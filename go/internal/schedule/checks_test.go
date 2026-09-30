package schedule

import (
	"context"
	"database/sql"
	"testing"
	"time"

	_ "modernc.org/sqlite"

	"github.com/valirum/quests/go/internal/domain"
	"github.com/valirum/quests/go/internal/events"
	"github.com/valirum/quests/go/internal/store"
	"github.com/valirum/quests/go/internal/timeutil"
)

const checksSchema = `
CREATE TABLE questcategory (
	id INTEGER PRIMARY KEY,
	slug TEXT NOT NULL,
	label TEXT NOT NULL,
	sort_order INTEGER NOT NULL DEFAULT 0,
	color TEXT NOT NULL DEFAULT '#9a9a9a',
	created_at DATETIME NOT NULL
);
CREATE TABLE questline (
	id INTEGER PRIMARY KEY,
	title TEXT NOT NULL,
	description TEXT NOT NULL DEFAULT '',
	category_id INTEGER,
	color TEXT NOT NULL DEFAULT '#9a9a9a',
	icon TEXT NOT NULL DEFAULT 'document',
	custom_icon TEXT,
	created_at DATETIME NOT NULL,
	updated_at DATETIME NOT NULL
);
CREATE TABLE quest (
	id INTEGER PRIMARY KEY,
	title TEXT NOT NULL,
	description TEXT NOT NULL DEFAULT '',
	status TEXT NOT NULL,
	significance TEXT NOT NULL,
	pinned INTEGER NOT NULL DEFAULT 0,
	sort_order INTEGER NOT NULL DEFAULT 0,
	deadline_at DATETIME,
	duration_seconds INTEGER,
	reward_attrs TEXT,
	category_id INTEGER,
	questline_id INTEGER,
	created_at DATETIME NOT NULL,
	updated_at DATETIME NOT NULL,
	completed_at DATETIME,
	template_id INTEGER,
	period_key TEXT,
	automated INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE queststep (
	id INTEGER PRIMARY KEY,
	quest_id INTEGER NOT NULL,
	title TEXT NOT NULL,
	description TEXT NOT NULL DEFAULT '',
	progress_current INTEGER NOT NULL DEFAULT 0,
	progress_total INTEGER NOT NULL DEFAULT 1,
	sort_order INTEGER NOT NULL DEFAULT 0,
	check_command TEXT,
	check_interval_seconds INTEGER,
	check_last_run_at DATETIME,
	wait_previous INTEGER NOT NULL DEFAULT 0,
	run_mode TEXT NOT NULL DEFAULT 'poll',
	run_status TEXT
);
CREATE TABLE questchangelog (
	id INTEGER PRIMARY KEY,
	at DATETIME NOT NULL,
	kind TEXT NOT NULL,
	quest_id INTEGER,
	title TEXT NOT NULL DEFAULT '',
	detail TEXT NOT NULL DEFAULT '',
	significance TEXT,
	revision INTEGER,
	comment TEXT
);
CREATE TABLE metricledger (
	id INTEGER PRIMARY KEY,
	quest_id INTEGER,
	reason TEXT
);
CREATE TABLE tag (
	id INTEGER PRIMARY KEY,
	slug TEXT NOT NULL UNIQUE,
	label TEXT NOT NULL,
	color TEXT NOT NULL DEFAULT '#9a9a9a',
	created_at DATETIME NOT NULL
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
);
`

func openChecksDB(t *testing.T) *store.Store {
	t.Helper()
	db, err := sql.Open("sqlite", "file:checks_"+t.Name()+"?mode=memory&cache=shared")
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { _ = db.Close() })
	db.SetMaxOpenConns(1)
	if _, err := db.Exec(checksSchema); err != nil {
		t.Fatal(err)
	}
	return &store.Store{DB: db}
}

func TestParseCheckStdout(t *testing.T) {
	n, ok := ParseCheckStdout("3\n")
	if !ok || n != 3 {
		t.Fatalf("got %d %v", n, ok)
	}
	n, ok = ParseCheckStdout("files: 12")
	if !ok || n != 12 {
		t.Fatalf("got %d %v", n, ok)
	}
	if _, ok := ParseCheckStdout("nope"); ok {
		t.Fatal("expected miss")
	}
}

func TestParseCheckOutputJSON(t *testing.T) {
	got := ParseCheckOutput(`{"progress": 4, "description": "половина"}`)
	if !got.ProgressOK || got.Progress != 4 {
		t.Fatalf("progress=%d ok=%v", got.Progress, got.ProgressOK)
	}
	if got.Description == nil || *got.Description != "половина" {
		t.Fatalf("description=%v", got.Description)
	}

	bare := ParseCheckOutput("2\n")
	if !bare.ProgressOK || bare.Progress != 2 || bare.Description != nil {
		t.Fatalf("bare=%+v", bare)
	}

	broken := ParseCheckOutput(`{not json`)
	if broken.ProgressOK || broken.Description != nil {
		t.Fatalf("broken should not update: %+v", broken)
	}

	noProgress := ParseCheckOutput(`{"description": "только текст"}`)
	if noProgress.ProgressOK {
		t.Fatal("missing progress must not set ProgressOK")
	}
	if noProgress.Description == nil || *noProgress.Description != "только текст" {
		t.Fatalf("description=%v", noProgress.Description)
	}

	badProgress := ParseCheckOutput(`{"progress": "x", "description": "keep?"}`)
	if badProgress.ProgressOK {
		t.Fatal("non-int progress must not set ProgressOK")
	}
}

func seedQuest(t *testing.T, st *store.Store, steps []domain.Step) domain.Quest {
	t.Helper()
	now := timeutil.NowUTC()
	q, err := st.CreateQuest(context.Background(), domain.Quest{
		Title: "auto", Status: domain.StatusActive, Significance: domain.SigCommon,
		CreatedAt: now, UpdatedAt: now, Automated: true, Steps: steps,
	})
	if err != nil {
		t.Fatal(err)
	}
	return q
}

func TestCheckPollProgress(t *testing.T) {
	st := openChecksDB(t)
	cmd := "echo 2"
	iv := 15
	q := seedQuest(t, st, []domain.Step{{
		Title: "poll", ProgressTotal: 5, SortOrder: 0,
		CheckCommand: &cmd, CheckIntervalSeconds: &iv, RunMode: domain.RunModePoll,
	}})
	r := NewCheckRunner(st, events.New())
	r.Tick(context.Background())
	r.Wait()
	got, err := st.GetQuest(context.Background(), q.ID)
	if err != nil {
		t.Fatal(err)
	}
	if got.Steps[0].ProgressCurrent != 2 {
		t.Fatalf("progress=%d want 2", got.Steps[0].ProgressCurrent)
	}
}

func TestCheckPollJSON(t *testing.T) {
	st := openChecksDB(t)
	cmd := `printf '{"progress":1,"description":"из JSON"}'`
	iv := 15
	q := seedQuest(t, st, []domain.Step{{
		Title: "poll-json", ProgressTotal: 2, SortOrder: 0,
		CheckCommand: &cmd, CheckIntervalSeconds: &iv, RunMode: domain.RunModePoll,
	}})
	r := NewCheckRunner(st, events.New())
	r.Tick(context.Background())
	r.Wait()
	got, err := st.GetQuest(context.Background(), q.ID)
	if err != nil {
		t.Fatal(err)
	}
	if got.Steps[0].ProgressCurrent != 1 {
		t.Fatalf("progress=%d", got.Steps[0].ProgressCurrent)
	}
	if got.Steps[0].Description != "из JSON" {
		t.Fatalf("description=%q", got.Steps[0].Description)
	}
	if got.Status != domain.StatusActive {
		t.Fatalf("status=%s", got.Status)
	}
}

func TestCheckPollJSONBrokenKeepsDescription(t *testing.T) {
	st := openChecksDB(t)
	cmd := `printf 'not-json'`
	iv := 15
	q := seedQuest(t, st, []domain.Step{{
		Title: "poll-broken", Description: "оставить", ProgressTotal: 2, SortOrder: 0,
		CheckCommand: &cmd, CheckIntervalSeconds: &iv, RunMode: domain.RunModePoll,
		ProgressCurrent: 1,
	}})
	r := NewCheckRunner(st, events.New())
	r.Tick(context.Background())
	r.Wait()
	got, err := st.GetQuest(context.Background(), q.ID)
	if err != nil {
		t.Fatal(err)
	}
	if got.Steps[0].Description != "оставить" {
		t.Fatalf("description wiped: %q", got.Steps[0].Description)
	}
	if got.Steps[0].ProgressCurrent != 1 {
		t.Fatalf("progress changed: %d", got.Steps[0].ProgressCurrent)
	}
}

func TestCheckWaitPrevious(t *testing.T) {
	st := openChecksDB(t)
	cmd1 := "true"
	cmd2 := "true"
	idle := domain.RunIdle
	q := seedQuest(t, st, []domain.Step{
		{
			Title: "one", ProgressTotal: 1, SortOrder: 0,
			CheckCommand: &cmd1, RunMode: domain.RunModeOnce, RunStatus: &idle,
		},
		{
			Title: "two", ProgressTotal: 1, SortOrder: 1,
			CheckCommand: &cmd2, RunMode: domain.RunModeOnce, RunStatus: &idle,
			WaitPrevious: true,
		},
	})
	r := NewCheckRunner(st, events.New())
	r.Tick(context.Background())
	r.Wait()
	got, err := st.GetQuest(context.Background(), q.ID)
	if err != nil {
		t.Fatal(err)
	}
	if !got.Steps[0].Done {
		t.Fatal("first step should complete on first tick")
	}
	if got.Steps[1].Done {
		t.Fatal("second step must wait for previous")
	}
	r.Tick(context.Background())
	r.Wait()
	got, err = st.GetQuest(context.Background(), q.ID)
	if err != nil {
		t.Fatal(err)
	}
	if !got.Steps[1].Done {
		t.Fatal("second step should run after previous is done")
	}
}

func TestCheckOnceFailQuest(t *testing.T) {
	st := openChecksDB(t)
	cmd := "false"
	idle := domain.RunIdle
	q := seedQuest(t, st, []domain.Step{{
		Title: "boom", ProgressTotal: 1, SortOrder: 0,
		CheckCommand: &cmd, RunMode: domain.RunModeOnce, RunStatus: &idle,
	}})
	r := NewCheckRunner(st, events.New())
	r.Tick(context.Background())
	r.Wait()
	got, err := st.GetQuest(context.Background(), q.ID)
	if err != nil {
		t.Fatal(err)
	}
	if got.Status != domain.StatusFailed {
		t.Fatalf("status=%s want failed", got.Status)
	}
	if got.Steps[0].RunStatus == nil || *got.Steps[0].RunStatus != domain.RunFail {
		t.Fatalf("run_status=%v", got.Steps[0].RunStatus)
	}
	var comment sql.NullString
	err = st.DB.QueryRow(`SELECT comment FROM questchangelog WHERE kind='quest_failed' ORDER BY id DESC LIMIT 1`).Scan(&comment)
	if err != nil || !comment.Valid || comment.String == "" {
		t.Fatalf("expected changelog comment, err=%v comment=%v", err, comment)
	}
}

func TestFailStaleRunning(t *testing.T) {
	st := openChecksDB(t)
	cmd := "sleep 99"
	run := domain.RunRunning
	q := seedQuest(t, st, []domain.Step{{
		Title: "stuck", ProgressTotal: 1, SortOrder: 0,
		CheckCommand: &cmd, RunMode: domain.RunModeOnce, RunStatus: &run,
	}})
	r := NewCheckRunner(st, events.New())
	r.FailStaleRunning(context.Background())
	got, err := st.GetQuest(context.Background(), q.ID)
	if err != nil {
		t.Fatal(err)
	}
	if got.Status != domain.StatusFailed {
		t.Fatalf("status=%s", got.Status)
	}
	_ = time.Second
}
