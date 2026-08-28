package httpapi

import (
	"bytes"
	"encoding/json"
	"net/http"
	"os"
	"os/exec"
	"strings"
)

// registerLLMActions wires the web-form path for the LLM action-batch
// feature: free text -> Groq -> dry-run preview -> (user confirms) -> apply.
// Both handlers shell into the same Python CLI subcommands used for manual
// testing (`quests llm-action-preview` / `quests llm-action-apply`), the
// same way cmdLLMAdd in go/internal/cli/run.go shells into `quests llm-add`.
func (s *Server) registerLLMActions(mux *http.ServeMux) {
	mux.HandleFunc("POST /api/llm/actions/preview", s.postLLMActionsPreview)
	mux.HandleFunc("POST /api/llm/actions/apply", s.postLLMActionsApply)
}

func (s *Server) runPythonCLI(subcommand string, extraArgs []string, stdin []byte) ([]byte, int, error) {
	args := []string{"run", "--directory", s.Root, "python", "-m", "quests.cli", subcommand, "--json"}
	args = append(args, extraArgs...)
	cmd := exec.Command("uv", args...)
	cmd.Env = append(os.Environ(), "QUESTS_CLI_NATIVE=1")
	if stdin != nil {
		cmd.Stdin = bytes.NewReader(stdin)
	}
	var stdout, stderr bytes.Buffer
	cmd.Stdout = &stdout
	cmd.Stderr = &stderr
	err := cmd.Run()
	exitCode := 0
	if ee, ok := err.(*exec.ExitError); ok {
		exitCode = ee.ExitCode()
		err = nil
	}
	if err != nil {
		return nil, 1, err
	}
	out := stdout.Bytes()
	if len(bytes.TrimSpace(out)) == 0 {
		out = stderr.Bytes()
	}
	return out, exitCode, nil
}

func (s *Server) postLLMActionsPreview(w http.ResponseWriter, r *http.Request) {
	var body struct {
		Text string `json:"text"`
	}
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
		writeErr(w, http.StatusBadRequest, "invalid JSON")
		return
	}
	text := strings.TrimSpace(body.Text)
	if text == "" {
		writeErr(w, http.StatusBadRequest, "text is required")
		return
	}
	out, _, err := s.runPythonCLI("llm-action-preview", []string{text}, nil)
	if err != nil {
		writeErr(w, http.StatusBadGateway, err.Error())
		return
	}
	relayCLIJSON(w, out)
}

func (s *Server) postLLMActionsApply(w http.ResponseWriter, r *http.Request) {
	var body struct {
		Batch json.RawMessage `json:"batch"`
	}
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil || len(body.Batch) == 0 {
		writeErr(w, http.StatusBadRequest, "batch is required")
		return
	}
	out, _, err := s.runPythonCLI("llm-action-apply", nil, body.Batch)
	if err != nil {
		writeErr(w, http.StatusBadGateway, err.Error())
		return
	}
	relayCLIJSON(w, out)
}

// relayCLIJSON forwards the CLI's own --json output as-is (it already
// carries {ok, ...} / {ok:false, detail} shapes); falls back to a wrapped
// error if the subprocess printed something that isn't JSON.
func relayCLIJSON(w http.ResponseWriter, out []byte) {
	var probe json.RawMessage
	if err := json.Unmarshal(out, &probe); err != nil {
		writeErr(w, http.StatusBadGateway, strings.TrimSpace(string(out)))
		return
	}
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	_, _ = w.Write(out)
}
