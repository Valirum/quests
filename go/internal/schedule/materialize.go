package schedule

import (
	"bytes"
	"context"
	"database/sql"
	"encoding/json"
	"math/rand"
	"os"
	"os/exec"
	"strconv"
	"strings"
	"time"

	"github.com/valirum/quests/go/internal/domain"
	"github.com/valirum/quests/go/internal/events"
	"github.com/valirum/quests/go/internal/store"
	"github.com/valirum/quests/go/internal/timeutil"
)

// emitPoolTimeout bounds how long emit_pool_command may run per attempt.
const emitPoolTimeout = 20 * time.Second

// emitPoolMaxAttempts caps retries of a failing/invalid emit_pool_command
// within one period before giving up (outcome=error) until the next period.
const emitPoolMaxAttempts = 3

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
	EmitPoolCommand sql.NullString
	EmitPoolPick    int
	RewardAttrs     sql.NullString
	CategoryID      sql.NullInt64
	QuestlineID     sql.NullInt64
	Automated       bool
}

type templateStepRow struct {
	Title                string
	Description          string
	SortOrder            int
	ProgressMin          int
	ProgressMax          int
	CheckCommand         sql.NullString
	CheckIntervalSeconds sql.NullInt64
	WaitPrevious         bool
	RunMode              string
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
			emit_window_start, emit_window_end, emit_pool_command, emit_pool_pick,
			reward_attrs, category_id, questline_id, automated
		FROM questtemplate WHERE enabled = 1 ORDER BY sort_order, id`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var templates []templateRow
	for rows.Next() {
		var t templateRow
		var pinned, enabled, automated int
		if err := rows.Scan(
			&t.ID, &t.Title, &t.Description, &pinned, &t.SortOrder, &t.DurationSeconds, &t.Freq, &t.Weekdays,
			&enabled, &t.Timezone, &t.DeadlineTime, &t.Significance, &t.EmitMode, &t.EmitChance,
			&t.EmitWindowStart, &t.EmitWindowEnd, &t.EmitPoolCommand, &t.EmitPoolPick,
			&t.RewardAttrs, &t.CategoryID, &t.QuestlineID, &automated,
		); err != nil {
			return nil, err
		}
		t.Pinned = pinned != 0
		t.Enabled = enabled != 0
		t.Automated = automated != 0
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

		usePool := tmpl.EmitPoolCommand.Valid && strings.TrimSpace(tmpl.EmitPoolCommand.String) != ""
		var poolRollID int64
		var steps []domain.Step
		if usePool {
			items, rollID, perr := resolveEmitPool(ctx, st, tmpl, key, now, rng)
			if perr != nil {
				return created, perr
			}
			poolRollID = rollID
			if len(items) == 0 {
				// retry pending, empty/zero-weight pool (miss), or attempts exhausted (error)
				continue
			}
			steps = stepsFromPoolItems(items)
		} else {
			steps, err = loadTemplateSteps(ctx, st, tmpl, rng)
			if err != nil {
				return created, err
			}
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
			Automated:       tmpl.Automated,
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
		if usePool && poolRollID != 0 {
			_, _ = st.DB.ExecContext(ctx, `
				UPDATE templateemitroll SET outcome = 'materialized', updated_at = ? WHERE id = ?`,
				timeutil.ToDBUTC(now), poolRollID)
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
			Automated:    createdQ.Automated,
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
		SELECT title, description, sort_order, progress_min, progress_max, check_command, check_interval_seconds,
			wait_previous, run_mode
		FROM questtemplatestep WHERE template_id = ? ORDER BY sort_order, id`, tmpl.ID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var src []templateStepRow
	for rows.Next() {
		var s templateStepRow
		var waitPrev int
		var runMode sql.NullString
		if err := rows.Scan(&s.Title, &s.Description, &s.SortOrder, &s.ProgressMin, &s.ProgressMax, &s.CheckCommand, &s.CheckIntervalSeconds, &waitPrev, &runMode); err != nil {
			return nil, err
		}
		s.WaitPrevious = waitPrev != 0
		s.RunMode = domain.RunModePoll
		if runMode.Valid {
			s.RunMode = store.NormalizeRunMode(runMode.String)
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
			st.WaitPrevious = s.WaitPrevious
			st.RunMode = s.RunMode
			if st.RunMode == domain.RunModePoll {
				iv := 15
				if s.CheckIntervalSeconds.Valid {
					iv = int(s.CheckIntervalSeconds.Int64)
					if iv < 15 {
						iv = 15
					}
				}
				st.CheckIntervalSeconds = &iv
			} else if s.CheckIntervalSeconds.Valid {
				iv := int(s.CheckIntervalSeconds.Int64)
				if iv >= 15 {
					st.CheckIntervalSeconds = &iv
				}
			}
			if st.RunMode == domain.RunModeOnce {
				idle := domain.RunIdle
				st.RunStatus = &idle
			}
		}
		out = append(out, st)
	}
	return out, nil
}

// poolItem is one entry of the JSON array printed by emit_pool_command.
type poolItem struct {
	Title       string   `json:"title"`
	Description string   `json:"description"`
	Weight      *float64 `json:"weight"`
	Ref         string   `json:"ref"`
}

func (it poolItem) effectiveWeight() float64 {
	if it.Weight == nil {
		return 1
	}
	if *it.Weight < 0 {
		return 0
	}
	return *it.Weight
}

func (it poolItem) key() string {
	if strings.TrimSpace(it.Ref) != "" {
		return it.Ref
	}
	return it.Title + "\x00" + it.Description
}

// resolveEmitPool drives one template's emit_pool_command for the current
// period: executes it (with retry-on-failure up to emitPoolMaxAttempts),
// weighted-picks emit_pool_pick items excluding recent picks, and persists
// state in templateemitroll so repeated ticks don't re-roll or re-exec.
// Returns an empty slice when there is nothing to materialize this tick
// (pending retry, empty/zero-weight pool = miss, or attempts exhausted).
func resolveEmitPool(ctx context.Context, st *store.Store, tmpl templateRow, periodKey string, now time.Time, rng *rand.Rand) ([]poolItem, int64, error) {
	var id int64
	var outcome string
	var attempts int
	var pickedRefs sql.NullString
	isNew := false
	err := st.DB.QueryRowContext(ctx, `
		SELECT id, outcome, attempts, picked_refs FROM templateemitroll
		WHERE template_id = ? AND period_key = ?`, tmpl.ID, periodKey).
		Scan(&id, &outcome, &attempts, &pickedRefs)
	if err == sql.ErrNoRows {
		isNew = true
	} else if err != nil {
		return nil, 0, err
	}
	if !isNew && (outcome == "materialized" || outcome == "error" || outcome == "miss") {
		return nil, id, nil
	}

	items, execErr := execEmitPoolCommand(ctx, tmpl.EmitPoolCommand.String)
	if execErr != nil {
		attempts++
		newOutcome := "scheduled"
		if attempts >= emitPoolMaxAttempts {
			newOutcome = "error"
		}
		if isNew {
			res, err := st.DB.ExecContext(ctx, `
				INSERT INTO templateemitroll (template_id, period_key, outcome, attempts, created_at, updated_at)
				VALUES (?, ?, ?, ?, ?, ?)`,
				tmpl.ID, periodKey, newOutcome, attempts, timeutil.ToDBUTC(now), timeutil.ToDBUTC(now))
			if err != nil {
				return nil, 0, err
			}
			id, _ = res.LastInsertId()
		} else {
			if _, err := st.DB.ExecContext(ctx, `
				UPDATE templateemitroll SET outcome = ?, attempts = ?, updated_at = ? WHERE id = ?`,
				newOutcome, attempts, timeutil.ToDBUTC(now), id); err != nil {
				return nil, 0, err
			}
		}
		return nil, id, nil
	}

	positive := make([]poolItem, 0, len(items))
	for _, it := range items {
		if it.effectiveWeight() > 0 {
			positive = append(positive, it)
		}
	}
	if len(positive) == 0 {
		if err := persistEmitPoolOutcome(ctx, st, id, isNew, tmpl.ID, periodKey, "miss", attempts, "", now); err != nil {
			return nil, 0, err
		}
		return nil, id, nil
	}

	excludeDepth := len(positive) - 1
	excluded := map[string]struct{}{}
	if excludeDepth > 0 {
		rows, err := st.DB.QueryContext(ctx, `
			SELECT picked_refs FROM templateemitroll
			WHERE template_id = ? AND period_key != ? AND picked_refs IS NOT NULL
			ORDER BY period_key DESC LIMIT ?`, tmpl.ID, periodKey, excludeDepth)
		if err != nil {
			return nil, 0, err
		}
		for rows.Next() {
			var raw string
			if err := rows.Scan(&raw); err != nil {
				rows.Close()
				return nil, 0, err
			}
			var keys []string
			if json.Unmarshal([]byte(raw), &keys) == nil {
				for _, k := range keys {
					excluded[k] = struct{}{}
				}
			}
		}
		if err := rows.Err(); err != nil {
			rows.Close()
			return nil, 0, err
		}
		rows.Close()
	}

	candidates := make([]poolItem, 0, len(positive))
	for _, it := range positive {
		if _, skip := excluded[it.key()]; !skip {
			candidates = append(candidates, it)
		}
	}
	m := tmpl.EmitPoolPick
	if m < 1 {
		m = 1
	}
	if len(candidates) < m {
		candidates = positive // not enough non-recent variants — fall back to the full pool
	}
	picked := weightedPickWithoutReplacement(candidates, m, rng)

	keys := make([]string, 0, len(picked))
	for _, it := range picked {
		keys = append(keys, it.key())
	}
	refsJSON, err := json.Marshal(keys)
	if err != nil {
		return nil, 0, err
	}
	if err := persistEmitPoolOutcome(ctx, st, id, isNew, tmpl.ID, periodKey, "scheduled", attempts, string(refsJSON), now); err != nil {
		return nil, 0, err
	}
	return picked, id, nil
}

func persistEmitPoolOutcome(ctx context.Context, st *store.Store, id int64, isNew bool, templateID int64, periodKey, outcome string, attempts int, pickedRefsJSON string, now time.Time) error {
	if isNew {
		_, err := st.DB.ExecContext(ctx, `
			INSERT INTO templateemitroll (template_id, period_key, outcome, attempts, picked_refs, created_at, updated_at)
			VALUES (?, ?, ?, ?, ?, ?, ?)`,
			templateID, periodKey, outcome, attempts, nullStrIfEmpty(pickedRefsJSON), timeutil.ToDBUTC(now), timeutil.ToDBUTC(now))
		return err
	}
	_, err := st.DB.ExecContext(ctx, `
		UPDATE templateemitroll SET outcome = ?, picked_refs = ?, updated_at = ? WHERE id = ?`,
		outcome, nullStrIfEmpty(pickedRefsJSON), timeutil.ToDBUTC(now), id)
	return err
}

func nullStrIfEmpty(s string) any {
	if s == "" {
		return nil
	}
	return s
}

// execEmitPoolCommand runs emit_pool_command and parses its stdout as a JSON
// array of pool items. A non-zero exit code or invalid JSON is an error —
// the caller treats it the same as a transient failure (counts an attempt).
//
// A value starting with a shebang is treated as an inline script body, not
// a shell one-liner: written to a temp file and executed directly so its
// own shebang picks the interpreter. This is deliberate — the script then
// lives in the template row (DB) instead of a path on whatever disk the
// server happens to run on, so nothing needs hand-deploying/scp'd when the
// server moves hosts. Secrets it needs go in the server's own root .env
// (already loaded into the process env by config.LoadDotenv, and passed
// through via cmd.Env below) rather than a script-adjacent .env file.
func execEmitPoolCommand(parent context.Context, command string) ([]poolItem, error) {
	ctx, cancel := context.WithTimeout(parent, emitPoolTimeout)
	defer cancel()

	var cmd *exec.Cmd
	if strings.HasPrefix(strings.TrimLeft(command, " \t\r\n"), "#!") {
		f, err := os.CreateTemp("", "quests-emit-pool-*")
		if err != nil {
			return nil, err
		}
		scriptPath := f.Name()
		defer os.Remove(scriptPath)
		_, writeErr := f.WriteString(command)
		closeErr := f.Close()
		if writeErr != nil {
			return nil, writeErr
		}
		if closeErr != nil {
			return nil, closeErr
		}
		if err := os.Chmod(scriptPath, 0o700); err != nil {
			return nil, err
		}
		cmd = exec.CommandContext(ctx, scriptPath)
	} else {
		cmd = exec.CommandContext(ctx, "sh", "-c", command)
	}

	cmd.Env = os.Environ()
	if home, err := os.UserHomeDir(); err == nil {
		cmd.Dir = home
	}
	var stdout, stderr bytes.Buffer
	cmd.Stdout = &stdout
	cmd.Stderr = &stderr
	if err := cmd.Run(); err != nil {
		return nil, err
	}
	var items []poolItem
	if err := json.Unmarshal(stdout.Bytes(), &items); err != nil {
		return nil, err
	}
	out := make([]poolItem, 0, len(items))
	for _, it := range items {
		if strings.TrimSpace(it.Title) == "" {
			continue
		}
		out = append(out, it)
	}
	return out, nil
}

// weightedPickWithoutReplacement draws up to m items from candidates,
// each draw weighted by effectiveWeight among what remains.
func weightedPickWithoutReplacement(candidates []poolItem, m int, rng *rand.Rand) []poolItem {
	pool := append([]poolItem(nil), candidates...)
	picked := make([]poolItem, 0, m)
	for len(picked) < m && len(pool) > 0 {
		total := 0.0
		for _, it := range pool {
			total += it.effectiveWeight()
		}
		if total <= 0 {
			break
		}
		r := rng.Float64() * total
		idx := len(pool) - 1
		acc := 0.0
		for j, it := range pool {
			acc += it.effectiveWeight()
			if r < acc {
				idx = j
				break
			}
		}
		picked = append(picked, pool[idx])
		pool = append(pool[:idx], pool[idx+1:]...)
	}
	return picked
}

func stepsFromPoolItems(items []poolItem) []domain.Step {
	out := make([]domain.Step, 0, len(items))
	for i, it := range items {
		desc := it.Description
		if strings.TrimSpace(it.Ref) != "" {
			if desc != "" {
				desc += "\n\n" + it.Ref
			} else {
				desc = it.Ref
			}
		}
		out = append(out, domain.Step{
			Title: it.Title, Description: desc,
			ProgressCurrent: 0, ProgressTotal: 1, SortOrder: i,
		})
	}
	return out
}
