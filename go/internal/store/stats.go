package store

import (
	"context"
	"database/sql"
	"os"
	"time"

	"github.com/valirum/quests/go/internal/timeutil"
)

func (s *Store) QuestIDForStep(ctx context.Context, stepID int64) (int64, error) {
	var qid sql.NullInt64
	err := s.DB.QueryRowContext(ctx, `SELECT quest_id FROM queststep WHERE id=?`, stepID).Scan(&qid)
	if err == sql.ErrNoRows || !qid.Valid {
		return 0, ErrNotFound
	}
	if err != nil {
		return 0, err
	}
	return qid.Int64, nil
}

func (s *Store) ListChangeLog(ctx context.Context, limit int, questID *int64, beforeID *int64) ([]map[string]any, error) {
	if limit < 1 {
		limit = 100
	}
	if limit > 500 {
		limit = 500
	}
	q := `SELECT id, at, kind, quest_id, title, detail, significance, revision
		FROM questchangelog WHERE 1=1`
	args := []any{}
	if questID != nil {
		q += ` AND quest_id=?`
		args = append(args, *questID)
	}
	if beforeID != nil {
		q += ` AND id < ?`
		args = append(args, *beforeID)
	}
	q += ` ORDER BY at DESC, id DESC LIMIT ?`
	args = append(args, limit)
	rows, err := s.DB.QueryContext(ctx, q, args...)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := make([]map[string]any, 0)
	for rows.Next() {
		var id int64
		var at, kind, title, detail string
		var nqid, nrev sql.NullInt64
		var nsig sql.NullString
		if err := rows.Scan(&id, &at, &kind, &nqid, &title, &detail, &nsig, &nrev); err != nil {
			return nil, err
		}
		t, _ := timeutil.ParseFlexible(at)
		m := map[string]any{
			"id": id, "at": derefISO(&t), "kind": kind, "quest_id": nil,
			"title": title, "detail": detail, "significance": nil, "revision": nil,
		}
		if nqid.Valid {
			m["quest_id"] = nqid.Int64
		}
		if nsig.Valid {
			m["significance"] = nsig.String
		}
		if nrev.Valid {
			m["revision"] = int(nrev.Int64)
		}
		out = append(out, m)
	}
	return out, rows.Err()
}

func (s *Store) BuildStats(ctx context.Context, days int, templateID *int64) (map[string]any, error) {
	if days < 1 {
		days = 30
	}
	if days > 366 {
		days = 366
	}
	tzName := os.Getenv("QUESTS_TZ")
	if tzName == "" {
		tzName = "Europe/Moscow"
	}
	loc, err := time.LoadLocation(tzName)
	if err != nil {
		loc = time.UTC
	}
	now := timeutil.NowUTC()
	today := now.In(loc)
	end := time.Date(today.Year(), today.Month(), today.Day(), 0, 0, 0, 0, loc)
	start := end.AddDate(0, 0, -(days - 1))

	daily := []map[string]any{}
	dailyMap := map[string]map[string]any{}
	for d := start; !d.After(end); d = d.AddDate(0, 0, 1) {
		key := d.Format("2006-01-02")
		row := map[string]any{"date": key, "issued": 0, "completed": 0, "failed": 0}
		daily = append(daily, row)
		dailyMap[key] = row
	}

	lo := start.UTC()
	hi := end.AddDate(0, 0, 1).UTC()
	rows, err := s.DB.QueryContext(ctx, `
		SELECT at, kind, quest_id FROM questchangelog
		WHERE at >= ? AND at < ? AND kind IN ('quest_created','quest_appeared','quest_completed','quest_failed')`,
		timeutil.ToDBUTC(lo), timeutil.ToDBUTC(hi))
	if err != nil {
		return nil, err
	}
	seen := map[string]struct{}{}
	for rows.Next() {
		var at, kind string
		var qid sql.NullInt64
		if err := rows.Scan(&at, &kind, &qid); err != nil {
			rows.Close()
			return nil, err
		}
		t, _ := timeutil.ParseFlexible(at)
		day := t.In(loc).Format("2006-01-02")
		bucket, ok := dailyMap[day]
		if !ok {
			continue
		}
		qkey := day + "|" + kind + "|"
		if qid.Valid {
			qkey += itoa64(qid.Int64)
		}
		if _, ok := seen[qkey]; ok {
			continue
		}
		seen[qkey] = struct{}{}
		switch kind {
		case "quest_created", "quest_appeared":
			bucket["issued"] = bucket["issued"].(int) + 1
		case "quest_completed":
			bucket["completed"] = bucket["completed"].(int) + 1
		case "quest_failed":
			bucket["failed"] = bucket["failed"].(int) + 1
		}
	}
	rows.Close()

	trows, err := s.DB.QueryContext(ctx, `SELECT id, title, enabled FROM questtemplate ORDER BY id`)
	if err != nil {
		return nil, err
	}
	templates := []map[string]any{}
	var firstEnabled, firstAny *int64
	for trows.Next() {
		var id int64
		var title string
		var en int
		_ = trows.Scan(&id, &title, &en)
		templates = append(templates, map[string]any{"id": id, "title": title, "enabled": en != 0})
		if firstAny == nil {
			v := id
			firstAny = &v
		}
		if en != 0 && firstEnabled == nil {
			v := id
			firstEnabled = &v
		}
	}
	trows.Close()

	chosen := templateID
	if chosen == nil {
		if firstEnabled != nil {
			chosen = firstEnabled
		} else {
			chosen = firstAny
		}
	}
	var tmplBlock map[string]any
	if chosen != nil {
		tmplBlock, err = s.templateStats(ctx, *chosen, now)
		if err == ErrNotFound {
			return nil, err
		}
	}

	return map[string]any{
		"range":     map[string]string{"from": start.Format("2006-01-02"), "to": end.Format("2006-01-02")},
		"daily":     daily,
		"templates": templates,
		"template":  tmplBlock,
	}, nil
}

func (s *Store) templateStats(ctx context.Context, templateID int64, now time.Time) (map[string]any, error) {
	var title string
	err := s.DB.QueryRowContext(ctx, `SELECT title FROM questtemplate WHERE id=?`, templateID).Scan(&title)
	if err != nil {
		return nil, ErrNotFound
	}
	rows, err := s.DB.QueryContext(ctx, `
		SELECT id, status, period_key, deadline_at FROM quest
		WHERE template_id=? AND period_key IS NOT NULL ORDER BY period_key`, templateID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	outcomes := []string{}
	bars := []map[string]any{}
	closed, total := 0, 0
	for rows.Next() {
		var id int64
		var status, pk string
		var deadline sql.NullString
		_ = rows.Scan(&id, &status, &pk, &deadline)
		outcome := "open"
		switch status {
		case "completed":
			outcome = "completed"
		case "failed", "delayed", "archived":
			outcome = "miss"
		default:
			if deadline.Valid {
				t, e := timeutil.ParseFlexible(deadline.String)
				if e == nil && !t.After(now) {
					outcome = "miss"
				}
			}
		}
		outcomes = append(outcomes, outcome)
		bars = append(bars, map[string]any{
			"period_key": pk, "status": status, "outcome": outcome, "quest_id": id,
		})
		total++
		if outcome != "open" {
			closed++
		}
	}
	cur, longest := computeStreaks(outcomes)
	rate := 0.0
	nClosed, nComp := 0, 0
	for _, o := range outcomes {
		if o == "open" {
			continue
		}
		nClosed++
		if o == "completed" {
			nComp++
		}
	}
	if nClosed > 0 {
		rate = float64(nComp) / float64(nClosed)
	}
	return map[string]any{
		"id": templateID, "title": title,
		"current_streak": cur, "longest_streak": longest,
		"closed": closed, "total": total, "close_rate": rate,
		"bars": bars,
	}, nil
}

func computeStreaks(outcomes []string) (current, longest int) {
	run := 0
	for _, o := range outcomes {
		if o == "completed" {
			run++
			if run > longest {
				longest = run
			}
		} else {
			run = 0
		}
	}
	i := len(outcomes) - 1
	for i >= 0 && outcomes[i] == "open" {
		i--
	}
	for i >= 0 && outcomes[i] == "completed" {
		current++
		i--
	}
	return current, longest
}
