package schedule

import (
	"context"

	"github.com/valirum/quests/go/internal/domain"
	"github.com/valirum/quests/go/internal/events"
	"github.com/valirum/quests/go/internal/store"
	"github.com/valirum/quests/go/internal/timeutil"
)

// ExpireOverdue marks active quests past deadline as delayed and publishes events.
func ExpireOverdue(ctx context.Context, st *store.Store, hub *events.Hub) ([]int64, error) {
	now := timeutil.NowUTC()
	nowDB := timeutil.ToDBUTC(now)
	rows, err := st.DB.QueryContext(ctx, `
		SELECT id FROM quest
		WHERE status = 'active' AND deadline_at IS NOT NULL AND deadline_at <= ?
		ORDER BY id`, nowDB)
	if err != nil {
		return nil, err
	}
	var ids []int64
	for rows.Next() {
		var id int64
		if err := rows.Scan(&id); err != nil {
			rows.Close()
			return nil, err
		}
		ids = append(ids, id)
	}
	rows.Close()
	if err := rows.Err(); err != nil {
		return nil, err
	}
	if len(ids) == 0 {
		return nil, nil
	}

	delayed := make([]int64, 0, len(ids))
	for _, id := range ids {
		q, err := st.GetQuest(ctx, id)
		if err != nil {
			continue
		}
		if q.Status != domain.StatusActive {
			continue
		}
		q.Status = domain.StatusDelayed
		q.UpdatedAt = now
		updated, err := st.UpdateQuest(ctx, q, "quest_delayed", "просрочено")
		if err != nil {
			return delayed, err
		}
		_ = st.ApplyQuestStatusRewards(ctx, updated, domain.StatusDelayed)
		qid := updated.ID
		hub.Publish("quest_delayed", events.PublishOpts{
			QuestID:      &qid,
			Title:        updated.Title,
			Description:  updated.Description,
			Detail:       "просрочено",
			Toast:        true,
			Source:       "system",
			Significance: string(updated.Significance),
		})
		delayed = append(delayed, qid)
	}
	return delayed, nil
}

// WindowNotifier fires quest_started once when the urgent window opens.
type WindowNotifier struct {
	notified map[int64]struct{}
	seeded   bool
}

func NewWindowNotifier() *WindowNotifier {
	return &WindowNotifier{notified: map[int64]struct{}{}}
}

func (w *WindowNotifier) Notify(ctx context.Context, st *store.Store, hub *events.Hub) ([]int64, error) {
	quests, err := st.ListQuests(ctx, store.ListFilter{})
	if err != nil {
		return nil, err
	}
	now := timeutil.NowUTC()
	inWindow := make([]domain.Quest, 0)
	live := map[int64]struct{}{}
	for _, q := range quests {
		if q.Status != domain.StatusActive || q.DeadlineAt == nil || q.DurationSeconds == nil {
			continue
		}
		rem := timeutil.RemainingSeconds(q.DeadlineAt, now)
		if rem != nil && *rem <= 0 {
			continue
		}
		if timeutil.IsInUrgentWindow(q.DeadlineAt, q.DurationSeconds, now) {
			inWindow = append(inWindow, q)
			live[q.ID] = struct{}{}
		}
	}
	for id := range w.notified {
		if _, ok := live[id]; !ok {
			delete(w.notified, id)
		}
	}
	if !w.seeded {
		for id := range live {
			w.notified[id] = struct{}{}
		}
		w.seeded = true
		return nil, nil
	}
	fired := make([]int64, 0)
	for _, q := range inWindow {
		if _, ok := w.notified[q.ID]; ok {
			continue
		}
		w.notified[q.ID] = struct{}{}
		qid := q.ID
		hub.Publish("quest_started", events.PublishOpts{
			QuestID:      &qid,
			Title:        q.Title,
			Description:  q.Description,
			Detail:       "началось задание",
			Toast:        true,
			Source:       "system",
			Significance: string(q.Significance),
		})
		fired = append(fired, qid)
	}
	return fired, nil
}
