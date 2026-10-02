package httpapi

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strconv"
	"strings"
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

func TestQuestStatusValidation(t *testing.T) {
	s := newAttachmentServer(t, "", "", 0)
	h := s.Handler()
	qid := seedQuest(t, s)
	url := "/api/quests/" + strconv.FormatInt(qid, 10)

	do := func(method, path string, body map[string]any) (int, string) {
		b, _ := json.Marshal(body)
		req := httptest.NewRequest(method, path, bytes.NewReader(b))
		req.Header.Set("Content-Type", "application/json")
		w := httptest.NewRecorder()
		h.ServeHTTP(w, req)
		return w.Code, w.Body.String()
	}

	code, msg := do(http.MethodPatch, url, map[string]any{"status": "delayed"})
	if code != http.StatusUnprocessableEntity {
		t.Fatalf("patch delayed: status %d want 422", code)
	}
	for _, want := range []string{"active", "frozen", "archived", `renamed to \"frozen\"`} {
		if !strings.Contains(msg, want) {
			t.Errorf("error %q should mention %q", msg, want)
		}
	}
	if code, _ := do(http.MethodPatch, url, map[string]any{"status": "frozen"}); code != http.StatusOK {
		t.Fatalf("patch frozen: status %d want 200", code)
	}
	if code, _ := do(http.MethodPost, "/api/quests", map[string]any{"title": "x", "status": "bogus"}); code != http.StatusUnprocessableEntity {
		t.Fatalf("create bogus status: %d want 422", code)
	}
	if code, _ := do(http.MethodGet, "/api/quests?status=bogus", nil); code != http.StatusUnprocessableEntity {
		t.Fatalf("list bogus status: %d want 422", code)
	}
	if _, msg := do(http.MethodPatch, url, map[string]any{"significance": "medium"}); !strings.Contains(msg, "insignificant") {
		t.Errorf("significance error %q should list valid values", msg)
	}
}
