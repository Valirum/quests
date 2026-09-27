package httpapi

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strconv"
	"testing"
)

// TestPatchQuestCategoryFollowsQuestline covers the drift bug: manually
// PATCHing category_id on a quest that already belongs to a questline with
// its own category must not stick — the questline's category always wins.
func TestPatchQuestCategoryFollowsQuestline(t *testing.T) {
	s := newAttachmentServer(t, "", "", 0)
	h := s.Handler()

	// Seed two categories and a questline pinned to the first one.
	var workCat, funCat int64
	for _, cat := range []struct {
		id   *int64
		slug string
	}{{&workCat, "work"}, {&funCat, "fun"}} {
		res, err := s.Store.DB.Exec(
			`INSERT INTO questcategory (slug, label, color, created_at) VALUES (?, ?, '#000000', datetime('now'))`,
			cat.slug, cat.slug,
		)
		if err != nil {
			t.Fatalf("insert category: %v", err)
		}
		id, _ := res.LastInsertId()
		*cat.id = id
	}
	res, err := s.Store.DB.Exec(
		`INSERT INTO questline (title, category_id, created_at, updated_at) VALUES ('line', ?, datetime('now'), datetime('now'))`,
		workCat,
	)
	if err != nil {
		t.Fatalf("insert questline: %v", err)
	}
	lineID, _ := res.LastInsertId()

	qid := seedQuest(t, s)

	// Assign the quest to the questline first (no category_id in this call).
	patch(t, h, qid, map[string]any{"questline_id": lineID})
	if got := questCategory(t, h, qid); got != workCat {
		t.Fatalf("after questline assign: category = %d, want %d", got, workCat)
	}

	// Now try to manually override the category on a quest that's already in
	// the questline — this is the bug: it used to stick.
	patch(t, h, qid, map[string]any{"category_id": funCat})
	if got := questCategory(t, h, qid); got != workCat {
		t.Fatalf("after manual category override: category = %d, want questline's %d (got %d)", workCat, workCat, got)
	}
}

func patch(t *testing.T, h http.Handler, qid int64, body map[string]any) {
	t.Helper()
	b, _ := json.Marshal(body)
	req := httptest.NewRequest(http.MethodPatch, "/api/quests/"+strconv.FormatInt(qid, 10), bytes.NewReader(b))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)
	if w.Code != http.StatusOK {
		t.Fatalf("patch quest %d: status %d: %s", qid, w.Code, w.Body.String())
	}
}

func questCategory(t *testing.T, h http.Handler, qid int64) int64 {
	t.Helper()
	req := httptest.NewRequest(http.MethodGet, "/api/quests/"+strconv.FormatInt(qid, 10), nil)
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)
	if w.Code != http.StatusOK {
		t.Fatalf("get quest %d: status %d: %s", qid, w.Code, w.Body.String())
	}
	var out struct {
		CategoryID *int64 `json:"category_id"`
	}
	if err := json.Unmarshal(w.Body.Bytes(), &out); err != nil {
		t.Fatalf("decode quest: %v", err)
	}
	if out.CategoryID == nil {
		t.Fatalf("quest %d has no category_id", qid)
	}
	return *out.CategoryID
}
