package httpapi

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strconv"
	"testing"
)

func TestQuestSignificanceValidation(t *testing.T) {
	s := newAttachmentServer(t, "", "", 0)
	h := s.Handler()
	qid := seedQuest(t, s)

	do := func(method, path string, body map[string]any) int {
		b, _ := json.Marshal(body)
		req := httptest.NewRequest(method, path, bytes.NewReader(b))
		req.Header.Set("Content-Type", "application/json")
		w := httptest.NewRecorder()
		h.ServeHTTP(w, req)
		return w.Code
	}
	url := "/api/quests/" + strconv.FormatInt(qid, 10)

	if got := do(http.MethodPatch, url, map[string]any{"significance": "medium"}); got != http.StatusUnprocessableEntity {
		t.Fatalf("patch invalid: status %d want 422", got)
	}
	if got := do(http.MethodPatch, url, map[string]any{"significance": ""}); got != http.StatusUnprocessableEntity {
		t.Fatalf("patch empty: status %d want 422", got)
	}
	if got := do(http.MethodPatch, url, map[string]any{"significance": "insignificant"}); got != http.StatusOK {
		t.Fatalf("patch insignificant: status %d want 200", got)
	}
	if got := do(http.MethodPost, "/api/quests", map[string]any{"title": "x", "significance": "low"}); got != http.StatusUnprocessableEntity {
		t.Fatalf("create invalid: status %d want 422", got)
	}
}
