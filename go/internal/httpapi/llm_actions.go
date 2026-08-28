package httpapi

import (
	"bytes"
	"io"
	"net/http"
	"os"
	"strings"
	"time"
)

// registerLLMActions wires the web-form path for the LLM action-batch
// feature: free text -> Groq -> dry-run preview -> (user confirms) -> apply.
// Both handlers proxy to the standalone quests-llm service (aiohttp,
// src/quests/llm/service.py) — a small long-lived process that owns the
// Groq/proxy networking concern, instead of shelling into a fresh `uv run`
// subprocess per request.
func (s *Server) registerLLMActions(mux *http.ServeMux) {
	mux.HandleFunc("POST /api/llm/actions/preview", s.postLLMActionsPreview)
	mux.HandleFunc("POST /api/llm/actions/apply", s.postLLMActionsApply)
}

func llmServiceBase() string {
	if v := strings.TrimSpace(os.Getenv("QUESTS_LLM_SERVICE_URL")); v != "" {
		return strings.TrimRight(v, "/")
	}
	return "http://127.0.0.1:8766"
}

var llmHTTPClient = &http.Client{Timeout: 120 * time.Second}

// proxyToLLMService forwards the request body as-is to the quests-llm
// service and relays its JSON response (and status code) back verbatim —
// that service already returns {ok, ...} / {ok:false, error} shapes.
func proxyToLLMService(w http.ResponseWriter, r *http.Request, path string) {
	body, err := io.ReadAll(r.Body)
	if err != nil {
		writeErr(w, http.StatusBadRequest, "invalid body")
		return
	}
	req, err := http.NewRequestWithContext(r.Context(), http.MethodPost, llmServiceBase()+path, bytes.NewReader(body))
	if err != nil {
		writeErr(w, http.StatusInternalServerError, err.Error())
		return
	}
	req.Header.Set("Content-Type", "application/json")

	resp, err := llmHTTPClient.Do(req)
	if err != nil {
		writeErr(w, http.StatusBadGateway, "quests-llm unreachable: "+err.Error())
		return
	}
	defer resp.Body.Close()

	out, err := io.ReadAll(resp.Body)
	if err != nil {
		writeErr(w, http.StatusBadGateway, err.Error())
		return
	}
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(resp.StatusCode)
	_, _ = w.Write(out)
}

func (s *Server) postLLMActionsPreview(w http.ResponseWriter, r *http.Request) {
	proxyToLLMService(w, r, "/preview")
}

func (s *Server) postLLMActionsApply(w http.ResponseWriter, r *http.Request) {
	proxyToLLMService(w, r, "/apply")
}
