package schedule

import (
	"context"
	"math/rand"
	"testing"

	"github.com/valirum/quests/go/internal/domain"
	"github.com/valirum/quests/go/internal/events"
	"github.com/valirum/quests/go/internal/store"
	"github.com/valirum/quests/go/internal/timeutil"
)

func seedQuestStatus(t *testing.T, st *store.Store, status domain.QuestStatus) domain.Quest {
	t.Helper()
	now := timeutil.NowUTC()
	q, err := st.CreateQuest(context.Background(), domain.Quest{
		Title: "seed", Status: status, Significance: domain.SigCommon,
		CreatedAt: now, UpdatedAt: now,
	})
	if err != nil {
		t.Fatal(err)
	}
	return q
}

func TestRemindDelayedNoneDelayed(t *testing.T) {
	st := openChecksDB(t)
	seedQuestStatus(t, st, domain.StatusActive)
	seedQuestStatus(t, st, domain.StatusExpired)

	hub := events.New()
	id, err := RemindDelayed(context.Background(), st, hub, rand.New(rand.NewSource(1)))
	if err != nil {
		t.Fatal(err)
	}
	if id != nil {
		t.Fatalf("expected no reminder, got quest=%d", *id)
	}
}

func TestRemindDelayedPicksOne(t *testing.T) {
	st := openChecksDB(t)
	seedQuestStatus(t, st, domain.StatusActive)
	a := seedQuestStatus(t, st, domain.StatusDelayed)
	b := seedQuestStatus(t, st, domain.StatusDelayed)

	hub := events.New()
	id, err := RemindDelayed(context.Background(), st, hub, rand.New(rand.NewSource(1)))
	if err != nil {
		t.Fatal(err)
	}
	if id == nil {
		t.Fatal("expected a reminder")
	}
	if *id != a.ID && *id != b.ID {
		t.Fatalf("got quest=%d, want one of %d/%d", *id, a.ID, b.ID)
	}
}

func TestRemindDelayedPublishesEvent(t *testing.T) {
	st := openChecksDB(t)
	q := seedQuestStatus(t, st, domain.StatusDelayed)

	hub := events.New()
	id, err := RemindDelayed(context.Background(), st, hub, rand.New(rand.NewSource(1)))
	if err != nil {
		t.Fatal(err)
	}
	if id == nil || *id != q.ID {
		t.Fatalf("got %v, want %d", id, q.ID)
	}
	evs := hub.EventsSince(0)
	if len(evs) != 1 {
		t.Fatalf("recent events = %d, want 1", len(evs))
	}
	p := evs[0]
	if p["kind"] != "quest_delayed_reminder" {
		t.Fatalf("kind = %v", p["kind"])
	}
	qid, _ := p["quest_id"].(*int64)
	if qid == nil || *qid != q.ID {
		t.Fatalf("quest_id = %v, want %d", p["quest_id"], q.ID)
	}
	if p["toast"] != true {
		t.Fatalf("toast = %v, want true", p["toast"])
	}
}
