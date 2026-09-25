package schedule

import (
	"context"
	"database/sql"
	"encoding/json"
	"math/rand"
	"testing"
	"time"

	_ "modernc.org/sqlite"

	"github.com/valirum/quests/go/internal/store"
)

const emitPoolSchema = `
CREATE TABLE templateemitroll (
	id INTEGER PRIMARY KEY,
	template_id INTEGER NOT NULL,
	period_key TEXT NOT NULL,
	outcome TEXT NOT NULL,
	scheduled_at DATETIME,
	attempts INTEGER NOT NULL DEFAULT 0,
	picked_refs TEXT,
	created_at DATETIME NOT NULL,
	updated_at DATETIME NOT NULL
);
`

func openEmitPoolDB(t *testing.T) *store.Store {
	t.Helper()
	db, err := sql.Open("sqlite", "file:emitpool_"+t.Name()+"?mode=memory&cache=shared")
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { _ = db.Close() })
	db.SetMaxOpenConns(1)
	if _, err := db.Exec(emitPoolSchema); err != nil {
		t.Fatal(err)
	}
	return &store.Store{DB: db}
}

func poolTemplate(id int64, command string, pick int) templateRow {
	return templateRow{
		ID:              id,
		EmitPoolCommand: sql.NullString{String: command, Valid: true},
		EmitPoolPick:    pick,
	}
}

// A pool of two equally-weighted items and pick=1 should, on the first
// call, schedule exactly one of them and persist it as the picked ref.
func TestResolveEmitPoolWeightedPickOne(t *testing.T) {
	st := openEmitPoolDB(t)
	tmpl := poolTemplate(1, `echo '[{"title":"a","weight":1},{"title":"b","weight":1}]'`, 1)
	rng := rand.New(rand.NewSource(1))

	items, rollID, failMsg, err := resolveEmitPool(context.Background(), st, tmpl, "2026-09-23", time.Now(), rng)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if failMsg != "" {
		t.Fatalf("unexpected failMsg: %q", failMsg)
	}
	if len(items) != 1 {
		t.Fatalf("want 1 item, got %d (%+v)", len(items), items)
	}
	if items[0].Title != "a" && items[0].Title != "b" {
		t.Fatalf("unexpected pick: %+v", items[0])
	}

	var outcome, picked string
	if err := st.DB.QueryRow(`SELECT outcome, picked_refs FROM templateemitroll WHERE id = ?`, rollID).
		Scan(&outcome, &picked); err != nil {
		t.Fatal(err)
	}
	if outcome != "scheduled" {
		t.Fatalf("want outcome=scheduled, got %q", outcome)
	}
	var refs []string
	if err := json.Unmarshal([]byte(picked), &refs); err != nil {
		t.Fatalf("picked_refs not JSON: %v", err)
	}
	if len(refs) != 1 {
		t.Fatalf("want 1 picked ref, got %v", refs)
	}
}

// emit_pool_pick <= 0 means "take everything new" — not a sample.
func TestResolveEmitPoolPickAllOnZero(t *testing.T) {
	st := openEmitPoolDB(t)
	tmpl := poolTemplate(1, `echo '[{"title":"a"},{"title":"b"},{"title":"c"}]'`, 0)

	items, _, _, err := resolveEmitPool(context.Background(), st, tmpl, "2026-09-23", time.Now(), rand.New(rand.NewSource(1)))
	if err != nil {
		t.Fatal(err)
	}
	if len(items) != 3 {
		t.Fatalf("want all 3 items, got %d (%+v)", len(items), items)
	}
}

// The anti-repeat filter excludes refs picked in the last period, so a
// pool of exactly two items with pick=1 must alternate across periods.
func TestResolveEmitPoolAntiRepeatAcrossPeriods(t *testing.T) {
	st := openEmitPoolDB(t)
	tmpl := poolTemplate(1, `echo '[{"title":"a","ref":"a"},{"title":"b","ref":"b"}]'`, 1)

	first, _, _, err := resolveEmitPool(context.Background(), st, tmpl, "period-1", time.Now(), rand.New(rand.NewSource(1)))
	if err != nil {
		t.Fatal(err)
	}
	if len(first) != 1 {
		t.Fatalf("want 1 item in period 1, got %d", len(first))
	}

	second, _, _, err := resolveEmitPool(context.Background(), st, tmpl, "period-2", time.Now(), rand.New(rand.NewSource(2)))
	if err != nil {
		t.Fatal(err)
	}
	if len(second) != 1 {
		t.Fatalf("want 1 item in period 2, got %d", len(second))
	}
	if second[0].Ref == first[0].Ref {
		t.Fatalf("expected the other item after period 1 picked %q, got %q again", first[0].Ref, second[0].Ref)
	}
}

// A repeated call within the same period must not re-execute the command
// or re-roll — it returns the already-persisted outcome (a "miss" here,
// since the pool ends up empty after zero weights are filtered).
func TestResolveEmitPoolIdempotentWithinPeriod(t *testing.T) {
	st := openEmitPoolDB(t)
	tmpl := poolTemplate(1, `echo '[{"title":"a","weight":0}]'`, 1)
	rng := rand.New(rand.NewSource(1))

	items1, rollID1, _, err := resolveEmitPool(context.Background(), st, tmpl, "p", time.Now(), rng)
	if err != nil {
		t.Fatal(err)
	}
	if len(items1) != 0 {
		t.Fatalf("want a miss (zero weight), got %+v", items1)
	}

	items2, rollID2, failMsg2, err := resolveEmitPool(context.Background(), st, tmpl, "p", time.Now(), rng)
	if err != nil {
		t.Fatal(err)
	}
	if len(items2) != 0 || failMsg2 != "" {
		t.Fatalf("second call should stay a no-op miss, got items=%+v failMsg=%q", items2, failMsg2)
	}
	if rollID1 != rollID2 {
		t.Fatalf("expected the same roll row to be reused, got %d then %d", rollID1, rollID2)
	}
}

// A command that always fails must retry up to emitPoolMaxAttempts, then
// flip outcome to "error" and return a non-empty failMsg exactly once —
// the call that exhausts attempts, so the caller can materialize a failed
// quest carrying the trace.
func TestResolveEmitPoolRetryThenError(t *testing.T) {
	st := openEmitPoolDB(t)
	tmpl := poolTemplate(1, `exit 7`, 1)
	rng := rand.New(rand.NewSource(1))

	var lastRollID int64
	for i := 1; i <= emitPoolMaxAttempts; i++ {
		items, rollID, failMsg, err := resolveEmitPool(context.Background(), st, tmpl, "p", time.Now(), rng)
		if err != nil {
			t.Fatalf("attempt %d: unexpected error: %v", i, err)
		}
		if len(items) != 0 {
			t.Fatalf("attempt %d: want no items on a failing command, got %+v", i, items)
		}
		lastRollID = rollID
		var outcome string
		var attempts int
		if err := st.DB.QueryRow(`SELECT outcome, attempts FROM templateemitroll WHERE id = ?`, rollID).
			Scan(&outcome, &attempts); err != nil {
			t.Fatal(err)
		}
		if attempts != i {
			t.Fatalf("attempt %d: want attempts=%d, got %d", i, i, attempts)
		}
		if i < emitPoolMaxAttempts {
			if outcome != "scheduled" {
				t.Fatalf("attempt %d: want outcome=scheduled while retrying, got %q", i, outcome)
			}
			if failMsg != "" {
				t.Fatalf("attempt %d: want no failMsg before attempts are exhausted, got %q", i, failMsg)
			}
		} else {
			if outcome != "error" {
				t.Fatalf("attempt %d: want outcome=error once attempts are exhausted, got %q", i, outcome)
			}
			if failMsg == "" {
				t.Fatalf("attempt %d: want a non-empty failMsg on the attempt that flips to error", i)
			}
		}
	}

	// Once outcome=error, further calls in the same period are a no-op —
	// no more attempts, no failMsg (nothing new happened this call).
	items, rollID, failMsg, err := resolveEmitPool(context.Background(), st, tmpl, "p", time.Now(), rng)
	if err != nil {
		t.Fatal(err)
	}
	if len(items) != 0 || failMsg != "" {
		t.Fatalf("post-error call should be a silent no-op, got items=%+v failMsg=%q", items, failMsg)
	}
	if rollID != lastRollID {
		t.Fatalf("post-error call should report the same roll id, got %d want %d", rollID, lastRollID)
	}
}

// emitPoolOpenAt: the check window opens duration_seconds before the
// deadline, not at the deadline itself and not before that offset.
func TestEmitPoolOpenAt(t *testing.T) {
	deadline := time.Date(2026, 9, 25, 13, 0, 0, 0, time.UTC)
	openAt := emitPoolOpenAt(deadline, 3600)
	want := time.Date(2026, 9, 25, 12, 0, 0, 0, time.UTC)
	if !openAt.Equal(want) {
		t.Fatalf("want openAt=%v, got %v", want, openAt)
	}

	before := deadline.Add(-2 * time.Hour)
	after := deadline.Add(-30 * time.Minute)
	if !before.Before(openAt) {
		t.Fatalf("sanity: %v should be before openAt %v", before, openAt)
	}
	if before.Before(openAt) == after.Before(openAt) {
		t.Fatalf("openAt should separate before (%v) from after (%v)", before, after)
	}

	// deadline_time set but no duration_seconds: the gate must default the
	// missing duration to 0 (check right at deadline_time), not fall back to
	// fixedDeadline's own midnight-to-deadline placeholder — that placeholder
	// is for the resulting quest's own duration field, unrelated to the gate.
	if got := emitPoolOpenAt(deadline, 0); !got.Equal(deadline) {
		t.Fatalf("want openAt=deadline (%v) when duration=0, got %v", deadline, got)
	}
}
