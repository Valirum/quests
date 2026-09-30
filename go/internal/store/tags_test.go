package store

import (
	"context"
	"database/sql"
	"fmt"
	"path/filepath"
	"testing"

	_ "modernc.org/sqlite"
)

func openTagTestDB(t *testing.T) *Store {
	t.Helper()
	path := filepath.Join(t.TempDir(), "quests.db")
	raw, err := sql.Open("sqlite", path)
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { _ = raw.Close() })
	schema := `
CREATE TABLE tag (
  id INTEGER PRIMARY KEY,
  slug TEXT NOT NULL UNIQUE,
  label TEXT NOT NULL,
  color TEXT NOT NULL DEFAULT '#9a9a9a',
  created_at TEXT NOT NULL
);
CREATE TABLE quest_tag (
  quest_id INTEGER NOT NULL,
  tag_id INTEGER NOT NULL,
  PRIMARY KEY (quest_id, tag_id)
);
CREATE TABLE template_tag (
  template_id INTEGER NOT NULL,
  tag_id INTEGER NOT NULL,
  PRIMARY KEY (template_id, tag_id)
);`
	if _, err := raw.Exec(schema); err != nil {
		t.Fatal(err)
	}
	return &Store{DB: raw}
}

func TestNormalizeTagSlug(t *testing.T) {
	cases := map[string]string{
		"Frontend":  "frontend",
		"  API UI ": "api-ui",
		"MCP_tools": "mcp-tools",
		"фронт энд": "фронт-энд",
	}
	for in, want := range cases {
		if got := NormalizeTagSlug(in); got != want {
			t.Fatalf("%q → %q, want %q", in, got, want)
		}
	}
}

func TestCreateTagConflictReturnsExisting(t *testing.T) {
	st := openTagTestDB(t)
	ctx := context.Background()
	a, err := st.CreateTag(ctx, TagCreate{Slug: "frontend", Label: "Frontend"})
	if err != nil {
		t.Fatal(err)
	}
	b, err := st.CreateTag(ctx, TagCreate{Slug: "Frontend", Label: "Other"})
	if err != ErrConflict {
		t.Fatalf("err=%v want conflict", err)
	}
	if b.ID != a.ID {
		t.Fatalf("ids %d vs %d", b.ID, a.ID)
	}
}

func TestSetQuestTagsLimit(t *testing.T) {
	st := openTagTestDB(t)
	ctx := context.Background()
	var ids []int64
	for i := 0; i < 6; i++ {
		tg, err := st.CreateTag(ctx, TagCreate{Slug: fmt.Sprintf("tag-%d", i), Label: "t"})
		if err != nil {
			t.Fatal(err)
		}
		ids = append(ids, tg.ID)
	}
	if err := st.SetQuestTags(ctx, 1, ids); err != ErrTooManyTags {
		t.Fatalf("err=%v want too many", err)
	}
	if err := st.SetQuestTags(ctx, 1, ids[:5]); err != nil {
		t.Fatal(err)
	}
	m, err := st.loadTagsForQuests(ctx, []int64{1})
	if err != nil {
		t.Fatal(err)
	}
	if len(m[1]) != 5 {
		t.Fatalf("got %d tags", len(m[1]))
	}
}

func TestCopyTemplateTagsToQuest(t *testing.T) {
	st := openTagTestDB(t)
	ctx := context.Background()
	tg, err := st.CreateTag(ctx, TagCreate{Slug: "api", Label: "API"})
	if err != nil {
		t.Fatal(err)
	}
	if err := st.SetTemplateTags(ctx, 7, []int64{tg.ID}); err != nil {
		t.Fatal(err)
	}
	if err := st.CopyTemplateTagsToQuest(ctx, 7, 42); err != nil {
		t.Fatal(err)
	}
	m, err := st.loadTagsForQuests(ctx, []int64{42})
	if err != nil {
		t.Fatal(err)
	}
	if len(m[42]) != 1 || m[42][0].Slug != "api" {
		t.Fatalf("%v", m[42])
	}
}
