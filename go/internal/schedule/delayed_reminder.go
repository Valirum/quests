package schedule

import (
	"context"
	"log"
	"math/rand"
	"time"

	"github.com/valirum/quests/go/internal/domain"
	"github.com/valirum/quests/go/internal/events"
	"github.com/valirum/quests/go/internal/store"
)

// RunDelayedReminderLoop periodically nudges about one manually "delayed"
// quest — not a list, just "кстати, проверь X" every so often. interval<=0
// disables it. Unlike RunBackupLoop it doesn't fire immediately on startup:
// the whole point is "not on every visit", and a restart shouldn't count as
// one.
func RunDelayedReminderLoop(ctx context.Context, st *store.Store, hub *events.Hub, interval time.Duration, rng *rand.Rand) {
	if interval <= 0 {
		log.Printf("delayed-reminder: disabled (QUESTS_DELAYED_REMINDER_DAYS=0)")
		return
	}
	ticker := time.NewTicker(interval)
	defer ticker.Stop()
	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
		}
		if _, err := RemindDelayed(ctx, st, hub, rng); err != nil {
			log.Printf("delayed-reminder: %v", err)
		}
	}
}

// RemindDelayed picks one random "delayed" quest and publishes a quiet toast
// about it. Returns the quest id nudged, or nil if nothing is delayed.
func RemindDelayed(ctx context.Context, st *store.Store, hub *events.Hub, rng *rand.Rand) (*int64, error) {
	status := domain.StatusDelayed
	quests, err := st.ListQuests(ctx, store.ListFilter{Status: &status})
	if err != nil {
		return nil, err
	}
	if len(quests) == 0 {
		return nil, nil
	}
	q := quests[rng.Intn(len(quests))]
	qid := q.ID
	hub.Publish("quest_delayed_reminder", events.PublishOpts{
		QuestID:      &qid,
		Title:        q.Title,
		Description:  q.Description,
		Detail:       "кстати, проверь",
		Toast:        true,
		Source:       "system",
		Significance: string(q.Significance),
		Automated:    q.Automated,
	})
	return &qid, nil
}
