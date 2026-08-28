package httpapi

import (
	"context"
	"encoding/json"
	"net/http"
	"strings"
	"time"

	"github.com/valirum/quests/go/internal/llmassist"
)

// registerLLMActions wires the web-form path for the LLM action-batch
// feature: free text -> Groq -> dry-run preview -> (user confirms) -> apply.
// Runs in-process (llmassist package), calling this same server over
// loopback (SelfBase) for the actual quest CRUD — same code path the
// frontend/CLI use, just one hop shorter than going through a separate
// service/container.
func (s *Server) registerLLMActions(mux *http.ServeMux) {
	mux.HandleFunc("POST /api/llm/actions/preview", s.postLLMActionsPreview)
	mux.HandleFunc("POST /api/llm/actions/apply", s.postLLMActionsApply)
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

	ctx, cancel := context.WithTimeout(r.Context(), 3*time.Minute)
	defer cancel()
	settings := llmassist.LoadSettings()
	batch, err := llmassist.ExtractActionBatch(ctx, settings, text)
	if err != nil {
		writeJSON(w, http.StatusBadGateway, map[string]any{"ok": false, "error": err.Error()})
		return
	}
	if batch.NeedsClarification {
		writeJSON(w, http.StatusOK, map[string]any{
			"ok": false, "needs_clarification": true, "clarify_question": batch.ClarifyQuestion,
		})
		return
	}

	executor := llmassist.NewExecutor(s.SelfBase)
	preview, err := executor.Run(batch, true)
	if err != nil {
		writeJSON(w, http.StatusUnprocessableEntity, map[string]any{"ok": false, "error": err.Error()})
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{
		"ok": true, "needs_clarification": false, "batch": batch, "preview": preview,
	})
}

func (s *Server) postLLMActionsApply(w http.ResponseWriter, r *http.Request) {
	var body struct {
		Batch llmassist.ActionBatch `json:"batch"`
	}
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
		writeErr(w, http.StatusBadRequest, "invalid JSON")
		return
	}
	if len(body.Batch.Actions) == 0 {
		writeErr(w, http.StatusBadRequest, "batch is required")
		return
	}

	executor := llmassist.NewExecutor(s.SelfBase)
	results, err := executor.Run(body.Batch, false)
	if err != nil {
		writeJSON(w, http.StatusUnprocessableEntity, map[string]any{"ok": false, "error": err.Error(), "results": results})
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"ok": true, "results": results})
}
