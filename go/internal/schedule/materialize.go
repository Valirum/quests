package schedule

import (
	"context"
	"database/sql"
	"math/rand"
	"os"
	"strconv"
	"strings"
	"time"

	"github.com/valirum/quests/go/internal/domain"
	"github.com/valirum/quests/go/internal/events"
	"github.com/valirum/quests/go/internal/store"
	"github.com/valirum/quests/go/internal/timeutil"
)

func defaultTZ() string {
	if v := strings.TrimSpace(os.Getenv("QUESTS_TZ")); v != "" {
		return v
	}
	return "Europe/Moscow"
}

type templateRow struct {
	ID              int64
	Title           string
	Description     string
	Pinned          bool
	SortOrder       int
	DurationSeconds sql.NullInt64
	Freq            string
	Weekdays        string
	Enabled         bool
	Timezone        string
	DeadlineTime    sql.NullString
	Significance    string
	EmitMode        string
	EmitChance      float64
	EmitWindowStart sql.NullString
	EmitWindowEnd   sql.NullString
	RewardAttrs     sql.NullString
	CategoryID      sql.NullInt64
	QuestlineID     sql.NullInt64
}

type templateStepRow struct {
	Title                string
	Description          string
	SortOrder            int
	ProgressMin          int
	ProgressMax          int
	CheckCommand         sql.NullString
	CheckIntervalSeconds sql.NullInt64
}

// MaterializeDue creates quest instances for due templates (fixed + surprise).
func MaterializeDue(ctx context.Context, st *store.Store, hub *events.Hub, now time.Time, rng *rand.Rand) ([]int64, error) {
	if rng == nil {
		rng = rand.New(rand.NewSource(time.Now().UnixNano()))
	}
	if now.IsZero() {
		now = timeutil.NowUTC()
	}
	rows, err := st.DB.QueryContext(ctx, `
		SELECT id, title, description, pinned, sort_order, duration_seconds, freq, weekdays,
			enabled, timezone, deadline_time, significance, emit_mode, emit_chance,
			emit_window_start, emit_window_end, reward_attrs, category_id, questline_id
		FROM questtemplate WHERE enabled = 1 ORDER BY sort_order, id`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var templates []templateRow
	for rows.Next() {
		var t templateRow
		var pinned, enabled int
		if err := rows.Scan(
			&t.ID, &t.Title, &t.Description, &pinned, &t.SortOrder, &t.DurationSeconds, &t.Freq, &t.Weekdays,
			&enabled, &t.Timezone, &t.DeadlineTime, &t.Significance, &t.EmitMode, &t.EmitChance,
			&t.EmitWindowStart, &t.EmitWindowEnd, &t.RewardAttrs, &t.CategoryID, &t.QuestlineID,
		); err != nil {
			return nil, err
		}
		t.Pinned = pinned != 0
		t.Enabled = enabled != 0
		templates = append(templates, t)
	}
	if err := rows.Err(); err != nil {
		return nil, err
	}

	created := make([]int64, 0)
	for _, tmpl := range templates {
		tzName := tmpl.Timezone
		if tzName == "" {
			tzName = defaultTZ()
		}
		loc, err := time.LoadLocation(tzName)
		if err != nil {
			loc, _ = time.LoadLocation(defaultTZ())
			if loc == nil {
				loc = time.UTC
			}
		}
		localNow := now.In(loc)
		if !templateDueToday(tmpl.Freq, tmpl.Weekdays, localNow) {
			continue
		}
		key := localNow.Format("2006-01-02")

		var existing sql.NullInt64
		err = st.DB.QueryRowContext(ctx, `
			SELECT id FROM quest WHERE template_id = ? AND period_key = ? LIMIT 1`,
			tmpl.ID, key).Scan(&existing)
		if err == nil && existing.Valid {
			continue
		}
		if err != nil && err != sql.ErrNoRows {
			return created, err
		}

		emitMode := strings.ToLower(strings.TrimSpace(tmpl.EmitMode))
		var surpriseRollID sql.NullInt64
		var deadline *time.Time
		var duration *int

		if emitMode == "surprise" || emitMode == "random" || emitMode == "chance" {
			rollID, outcome, scheduledAt, err := ensureSurpriseRoll(ctx, st, tmpl, key, localNow, rng)
			if err != nil {
				return created, err
			}
			if outcome == "miss" || outcome == "materialized" {
				continue
			}
			if outcome == "scheduled" && scheduledAt != nil && now.Before(*scheduledAt) {
				continue
			}
			surpriseRollID = sql.NullInt64{Int64: rollID, Valid: true}
			deadline, duration = surpriseDeadline(tmpl, now)
		} else {
			deadline, duration = fixedDeadline(tmpl, localNow, loc)
		}

		steps, err := loadTemplateSteps(ctx, st, tmpl, rng)
		if err != nil {
			return created, err
		}

		q := domain.Quest{
			Title:           tmpl.Title,
			Description:     tmpl.Description,
			Status:          domain.StatusActive,
			Significance:    domain.Significance(tmpl.Significance),
			Pinned:          tmpl.Pinned,
			SortOrder:       tmpl.SortOrder,
			DeadlineAt:      deadline,
			DurationSeconds: duration,
			CreatedAt:       now,
			UpdatedAt:       now,
			Steps:           steps,
		}
		if tmpl.Significance == "" {
			q.Significance = domain.SigCommon
		}
		if tmpl.RewardAttrs.Valid {
			s := tmpl.RewardAttrs.String
			q.RewardAttrs = &s
		}
		if tmpl.CategoryID.Valid {
			v := tmpl.CategoryID.Int64
			q.CategoryID = &v
		}
		if tmpl.QuestlineID.Valid {
			v := tmpl.QuestlineID.Int64
			q.QuestlineID = &v
		}
		tid := tmpl.ID
		q.TemplateID = &tid
		pk := key
		q.PeriodKey = &pk

		// Create without auto quest_created — we emit quest_appeared.
		createdQ, err := st.CreateQuestAppeared(ctx, q)
		if err != nil {
			return created, err
		}
		if surpriseRollID.Valid {
			_, _ = st.DB.ExecContext(ctx, `
				UPDATE templateemitroll SET outcome = 'materialized', updated_at = ? WHERE id = ?`,
				timeutil.ToDBUTC(now), surpriseRollID.Int64)
		}
		qid := createdQ.ID
		detail := "Период " + key
		hub.Publish("quest_appeared", events.PublishOpts{
			QuestID:     &qid,
			Title:       createdQ.Title,
			Description: createdQ.Description,
			Detail:      detail,
			// Periodic materialization is routine, not something to notice —
			// a fullscreen major toast for every daily template at midnight
			// is exactly the "pack of identical alerts" this was meant to fix.
			Toast:        false,
			Source:       "system",
			Significance: string(createdQ.Significance),
			Sound:        strPtr("quest_created"),
		})
		created = append(created, qid)
	}
	return created, nil
}

func strPtr(s string) *string { return &s }

func templateDueToday(freq, weekdays string, localNow time.Time) bool {
	if strings.ToLower(freq) == "daily" || freq == "" {
		return true
	}
	days := parseWeekdays(weekdays)
	if len(days) == 0 {
		return true
	}
	// Python weekday(): Mon=0 … Sun=6. Go: Sun=0 … Sat=6.
	py := (int(localNow.Weekday()) + 6) % 7
	_, ok := days[py]
	return ok
}

// TemplateDueTodayForTest exports weekday matching for unit tests.
func TemplateDueTodayForTest(freq, weekdays string, localNow time.Time) bool {
	return templateDueToday(freq, weekdays, localNow)
}

func parseWeekdays(raw string) map[int]struct{} {
	out := map[int]struct{}{}
	for _, part := range strings.Split(raw, ",") {
		part = strings.TrimSpace(part)
		if part == "" {
			continue
		}
		n, err := strconv.Atoi(part)
		if err != nil || n < 0 || n > 6 {
			continue
		}
		out[n] = struct{}{}
	}
	return out
}

func parseClock(raw string) (hour, min, sec int, ok bool) {
	raw = strings.TrimSpace(raw)
	if raw == "" {
		return 0, 0, 0, false
	}
	parts := strings.Split(raw, ":")
	if len(parts) < 2 {
		return 0, 0, 0, false
	}
	h, err1 := strconv.Atoi(parts[0])
	m, err2 := strconv.Atoi(parts[1])
	s := 0
	if len(parts) > 2 {
		s, _ = strconv.Atoi(parts[2])
	}
	if err1 != nil || err2 != nil || h < 0 || h > 23 || m < 0 || m > 59 || s < 0 || s > 59 {
		return 0, 0, 0, false
	}
	return h, m, s, true
}

func fixedDeadline(tmpl templateRow, localNow time.Time, loc *time.Location) (*time.Time, *int) {
	if !tmpl.DeadlineTime.Valid {
		return nil, nil
	}
	h, m, s, ok := parseClock(tmpl.DeadlineTime.String)
	if !ok {
		return nil, nil
	}
	deadlineLocal := time.Date(localNow.Year(), localNow.Month(), localNow.Day(), h, m, s, 0, loc)
	deadlineUTC := deadlineLocal.UTC()
	var duration int
	if tmpl.DurationSeconds.Valid {
		duration = int(tmpl.DurationSeconds.Int64)
		if duration < 1 {
			duration = 1
		}
	} else {
		startLocal := time.Date(localNow.Year(), localNow.Month(), localNow.Day(), 0, 0, 0, 0, loc)
		if !deadlineLocal.After(startLocal) {
			startLocal = localNow
		}
		duration = int(deadlineLocal.Sub(startLocal).Seconds())
		if duration < 60 {
			duration = 60
		}
	}
	return &deadlineUTC, &duration
}

func surpriseDeadline(tmpl templateRow, nowUTC time.Time) (*time.Time, *int) {
	if !tmpl.DurationSeconds.Valid {
		return nil, nil
	}
	duration := int(tmpl.DurationSeconds.Int64)
	if duration < 1 {
		duration = 1
	}
	deadline := nowUTC.Add(time.Duration(duration) * time.Second)
	return &deadline, &duration
}

func ensureSurpriseRoll(ctx context.Context, st *store.Store, tmpl templateRow, periodKey string, localNow time.Time, rng *rand.Rand) (int64, string, *time.Time, error) {
	var id int64
	var outcome string
	var scheduled sql.NullString
	err := st.DB.QueryRowContext(ctx, `
		SELECT id, outcome, scheduled_at FROM templateemitroll
		WHERE template_id = ? AND period_key = ?`, tmpl.ID, periodKey).Scan(&id, &outcome, &scheduled)
	if err == nil {
		var sched *time.Time
		if scheduled.Valid {
			t, e := timeutil.ParseFlexible(scheduled.String)
			if e == nil {
				sched = &t
			}
		}
		return id, outcome, sched, nil
	}
	if err != sql.ErrNoRows {
		return 0, "", nil, err
	}

	chance := tmpl.EmitChance
	if chance < 0 {
		chance = 0
	}
	if chance > 1 {
		chance = 1
	}
	now := timeutil.NowUTC()
	if rng.Float64() >= chance {
		res, err := st.DB.ExecContext(ctx, `
			INSERT INTO templateemitroll (template_id, period_key, outcome, scheduled_at, created_at, updated_at)
			VALUES (?, ?, 'miss', NULL, ?, ?)`, tmpl.ID, periodKey, timeutil.ToDBUTC(now), timeutil.ToDBUTC(now))
		if err != nil {
			return 0, "", nil, err
		}
		id, _ = res.LastInsertId()
		return id, "miss", nil, nil
	}

	startRaw, endRaw := "", ""
	if tmpl.EmitWindowStart.Valid {
		startRaw = tmpl.EmitWindowStart.String
	}
	if tmpl.EmitWindowEnd.Valid {
		endRaw = tmpl.EmitWindowEnd.String
	}
	scheduledLocal := pickScheduledAt(localNow, startRaw, endRaw, rng)
	schedUTC := scheduledLocal.UTC()
	res, err := st.DB.ExecContext(ctx, `
		INSERT INTO templateemitroll (template_id, period_key, outcome, scheduled_at, created_at, updated_at)
		VALUES (?, ?, 'scheduled', ?, ?, ?)`,
		tmpl.ID, periodKey, timeutil.ToDBUTC(schedUTC), timeutil.ToDBUTC(now), timeutil.ToDBUTC(now))
	if err != nil {
		return 0, "", nil, err
	}
	id, _ = res.LastInsertId()
	return id, "scheduled", &schedUTC, nil
}

func pickScheduledAt(localDay time.Time, windowStart, windowEnd string, rng *rand.Rand) time.Time {
	sh, sm, ss, okS := parseClock(windowStart)
	eh, em, es, okE := parseClock(windowEnd)
	if !okS {
		sh, sm, ss = 0, 0, 0
	}
	if !okE {
		eh, em, es = 23, 59, 0
	}
	loc := localDay.Location()
	start := time.Date(localDay.Year(), localDay.Month(), localDay.Day(), sh, sm, ss, 0, loc)
	end := time.Date(localDay.Year(), localDay.Month(), localDay.Day(), eh, em, es, 0, loc)
	if end.Before(start) {
		start, end = end, start
	}
	span := int(end.Sub(start).Seconds())
	if span < 0 {
		span = 0
	}
	offset := 0
	if span > 0 {
		offset = rng.Intn(span + 1)
	}
	return start.Add(time.Duration(offset) * time.Second)
}

func loadTemplateSteps(ctx context.Context, st *store.Store, tmpl templateRow, rng *rand.Rand) ([]domain.Step, error) {
	rows, err := st.DB.QueryContext(ctx, `
		SELECT title, description, sort_order, progress_min, progress_max, check_command, check_interval_seconds
		FROM questtemplatestep WHERE template_id = ? ORDER BY sort_order, id`, tmpl.ID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var src []templateStepRow
	for rows.Next() {
		var s templateStepRow
		if err := rows.Scan(&s.Title, &s.Description, &s.SortOrder, &s.ProgressMin, &s.ProgressMax, &s.CheckCommand, &s.CheckIntervalSeconds); err != nil {
			return nil, err
		}
		src = append(src, s)
	}
	if len(src) == 0 {
		return []domain.Step{{Title: tmpl.Title, ProgressTotal: 1, SortOrder: 0}}, nil
	}
	out := make([]domain.Step, 0, len(src))
	for i, s := range src {
		lo, hi := s.ProgressMin, s.ProgressMax
		if lo < 1 {
			lo = 1
		}
		if hi < 1 {
			hi = 1
		}
		if hi < lo {
			lo, hi = hi, lo
		}
		total := lo
		if hi > lo {
			total = lo + rng.Intn(hi-lo+1)
		}
		st := domain.Step{
			Title: s.Title, Description: s.Description,
			ProgressCurrent: 0, ProgressTotal: total, SortOrder: s.SortOrder,
		}
		if st.SortOrder == 0 && i > 0 {
			st.SortOrder = i
		}
		if s.CheckCommand.Valid && strings.TrimSpace(s.CheckCommand.String) != "" {
			c := s.CheckCommand.String
			st.CheckCommand = &c
			iv := 15
			if s.CheckIntervalSeconds.Valid {
				iv = int(s.CheckIntervalSeconds.Int64)
				if iv < 15 {
					iv = 15
				}
			}
			st.CheckIntervalSeconds = &iv
		}
		out = append(out, st)
	}
	return out, nil
}
