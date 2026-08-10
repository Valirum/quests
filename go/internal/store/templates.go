package store

import (
	"context"
	"database/sql"
	"encoding/json"
	"strconv"
	"strings"

	"github.com/valirum/quests/go/internal/timeutil"
)

type TemplateRead map[string]any

func (s *Store) ListTemplates(ctx context.Context, enabled *bool) ([]TemplateRead, error) {
	q := `
		SELECT t.id, t.title, t.description, t.pinned, t.sort_order, t.duration_seconds, t.freq, t.weekdays,
			t.enabled, t.timezone, t.deadline_time, t.significance, t.emit_mode, t.emit_chance,
			t.emit_window_start, t.emit_window_end, t.reward_attrs, t.category_id, t.questline_id,
			t.created_at, t.updated_at,
			c.slug, c.label, c.color, l.title, l.color, l.icon, l.custom_icon, l.updated_at, l.id
		FROM questtemplate t
		LEFT JOIN questcategory c ON c.id = t.category_id
		LEFT JOIN questline l ON l.id = t.questline_id
		WHERE 1=1`
	args := []any{}
	if enabled != nil {
		q += ` AND t.enabled = ?`
		if *enabled {
			args = append(args, 1)
		} else {
			args = append(args, 0)
		}
	}
	q += ` ORDER BY t.sort_order, t.id`
	rows, err := s.DB.QueryContext(ctx, q, args...)
	if err != nil {
		return nil, err
	}
	out := make([]TemplateRead, 0)
	for rows.Next() {
		tr, err := scanTemplate(rows)
		if err != nil {
			rows.Close()
			return nil, err
		}
		out = append(out, tr)
	}
	if err := rows.Err(); err != nil {
		rows.Close()
		return nil, err
	}
	_ = rows.Close()
	for i := range out {
		id := int64(out[i]["id"].(int64))
		steps, err := s.loadTemplateStepsRead(ctx, id)
		if err != nil {
			return nil, err
		}
		out[i]["steps"] = steps
	}
	return out, nil
}

func (s *Store) GetTemplate(ctx context.Context, id int64) (TemplateRead, error) {
	row := s.DB.QueryRowContext(ctx, `
		SELECT t.id, t.title, t.description, t.pinned, t.sort_order, t.duration_seconds, t.freq, t.weekdays,
			t.enabled, t.timezone, t.deadline_time, t.significance, t.emit_mode, t.emit_chance,
			t.emit_window_start, t.emit_window_end, t.reward_attrs, t.category_id, t.questline_id,
			t.created_at, t.updated_at,
			c.slug, c.label, c.color, l.title, l.color, l.icon, l.custom_icon, l.updated_at, l.id
		FROM questtemplate t
		LEFT JOIN questcategory c ON c.id = t.category_id
		LEFT JOIN questline l ON l.id = t.questline_id
		WHERE t.id = ?`, id)
	tr, err := scanTemplate(row)
	if err == sql.ErrNoRows {
		return nil, ErrNotFound
	}
	if err != nil {
		return nil, err
	}
	steps, err := s.loadTemplateStepsRead(ctx, id)
	if err != nil {
		return nil, err
	}
	tr["steps"] = steps
	return tr, nil
}

func (s *Store) CreateTemplate(ctx context.Context, body map[string]any) (TemplateRead, error) {
	now := timeutil.NowUTC()
	title, _ := body["title"].(string)
	title = strings.TrimSpace(title)
	if title == "" {
		return nil, errBad("title required")
	}
	desc, _ := asString(body["description"])
	pinned := asBool(body["pinned"], false)
	sortOrder := asInt(body["sort_order"], 0)
	freq := asStringDef(body["freq"], "daily")
	weekdays := asStringDef(body["weekdays"], "0,1,2,3,4,5,6")
	enabled := asBool(body["enabled"], true)
	tz := asStringDef(body["timezone"], "Europe/Moscow")
	sig := asStringDef(body["significance"], "common")
	emitMode := asStringDef(body["emit_mode"], "fixed")
	emitChance := asFloat(body["emit_chance"], 1.0)
	colorCat := nullI64(asI64Ptr(body["category_id"]))
	lineID := nullI64(asI64Ptr(body["questline_id"]))

	res, err := s.DB.ExecContext(ctx, `
		INSERT INTO questtemplate (
			title, description, pinned, sort_order, duration_seconds, freq, weekdays, enabled, timezone,
			deadline_time, significance, emit_mode, emit_chance, emit_window_start, emit_window_end,
			reward_attrs, category_id, questline_id, created_at, updated_at
		) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
		title, desc, boolInt(pinned), sortOrder, nullInt(asIntPtr(body["duration_seconds"])), freq, weekdays, boolInt(enabled), tz,
		nullStr(asStringPtr(body["deadline_time"])), sig, emitMode, emitChance,
		nullStr(asStringPtr(body["emit_window_start"])), nullStr(asStringPtr(body["emit_window_end"])),
		nullStr(asStringPtr(body["reward_attrs"])), colorCat, lineID,
		timeutil.ToDBUTC(now), timeutil.ToDBUTC(now),
	)
	if err != nil {
		return nil, err
	}
	tid, _ := res.LastInsertId()
	if err := s.replaceTemplateSteps(ctx, tid, body["steps"]); err != nil {
		return nil, err
	}
	return s.GetTemplate(ctx, tid)
}

func (s *Store) UpdateTemplate(ctx context.Context, id int64, body map[string]any) (TemplateRead, error) {
	cur, err := s.GetTemplate(ctx, id)
	if err != nil {
		return nil, err
	}
	merged := map[string]any{}
	for k, v := range cur {
		merged[k] = v
	}
	for k, v := range body {
		merged[k] = v
	}
	now := timeutil.NowUTC()
	_, err = s.DB.ExecContext(ctx, `
		UPDATE questtemplate SET
			title=?, description=?, pinned=?, sort_order=?, duration_seconds=?, freq=?, weekdays=?,
			enabled=?, timezone=?, deadline_time=?, significance=?, emit_mode=?, emit_chance=?,
			emit_window_start=?, emit_window_end=?, reward_attrs=?, category_id=?, questline_id=?, updated_at=?
		WHERE id=?`,
		asStringDef(merged["title"], ""), asStringDef(merged["description"], ""),
		boolInt(asBool(merged["pinned"], false)), asInt(merged["sort_order"], 0),
		nullInt(asIntPtr(merged["duration_seconds"])), asStringDef(merged["freq"], "daily"),
		asStringDef(merged["weekdays"], "0,1,2,3,4,5,6"), boolInt(asBool(merged["enabled"], true)),
		asStringDef(merged["timezone"], "Europe/Moscow"), nullStr(asStringPtr(merged["deadline_time"])),
		asStringDef(merged["significance"], "common"), asStringDef(merged["emit_mode"], "fixed"),
		asFloat(merged["emit_chance"], 1.0), nullStr(asStringPtr(merged["emit_window_start"])),
		nullStr(asStringPtr(merged["emit_window_end"])), nullStr(asStringPtr(merged["reward_attrs"])),
		nullI64(asI64Ptr(merged["category_id"])), nullI64(asI64Ptr(merged["questline_id"])),
		timeutil.ToDBUTC(now), id,
	)
	if err != nil {
		return nil, err
	}
	if _, ok := body["steps"]; ok {
		if err := s.replaceTemplateSteps(ctx, id, body["steps"]); err != nil {
			return nil, err
		}
	}
	return s.GetTemplate(ctx, id)
}

func (s *Store) DeleteTemplate(ctx context.Context, id int64) error {
	tx, err := s.DB.BeginTx(ctx, nil)
	if err != nil {
		return err
	}
	defer func() { _ = tx.Rollback() }()
	if _, err := tx.ExecContext(ctx, `DELETE FROM templateemitroll WHERE template_id=?`, id); err != nil {
		return err
	}
	if _, err := tx.ExecContext(ctx, `DELETE FROM questtemplatestep WHERE template_id=?`, id); err != nil {
		return err
	}
	res, err := tx.ExecContext(ctx, `DELETE FROM questtemplate WHERE id=?`, id)
	if err != nil {
		return err
	}
	n, _ := res.RowsAffected()
	if n == 0 {
		return ErrNotFound
	}
	return tx.Commit()
}

func (s *Store) CopyTemplate(ctx context.Context, id int64) (TemplateRead, error) {
	src, err := s.GetTemplate(ctx, id)
	if err != nil {
		return nil, err
	}
	src["title"] = asStringDef(src["title"], "") + " (копия)"
	src["enabled"] = false
	delete(src, "id")
	delete(src, "created_at")
	delete(src, "updated_at")
	return s.CreateTemplate(ctx, src)
}

func (s *Store) replaceTemplateSteps(ctx context.Context, tid int64, raw any) error {
	_, _ = s.DB.ExecContext(ctx, `DELETE FROM questtemplatestep WHERE template_id=?`, tid)
	steps, ok := raw.([]any)
	if !ok {
		// try []map from json decode into map[string]any
		b, _ := json.Marshal(raw)
		_ = json.Unmarshal(b, &steps)
	}
	if len(steps) == 0 {
		_, err := s.DB.ExecContext(ctx, `
			INSERT INTO questtemplatestep (template_id, title, description, sort_order, progress_min, progress_max)
			VALUES (?, ?, '', 0, 1, 1)`, tid, "Шаг")
		return err
	}
	for i, item := range steps {
		m, _ := item.(map[string]any)
		if m == nil {
			b, _ := json.Marshal(item)
			_ = json.Unmarshal(b, &m)
		}
		title := strings.TrimSpace(asStringDef(m["title"], ""))
		if title == "" {
			continue
		}
		pmin := asInt(m["progress_min"], 0)
		pmax := asInt(m["progress_max"], 0)
		if pmin == 0 && pmax == 0 {
			pt := asInt(m["progress_total"], 1)
			pmin, pmax = pt, pt
		}
		if pmin < 1 {
			pmin = 1
		}
		if pmax < 1 {
			pmax = pmin
		}
		ord := asInt(m["sort_order"], i)
		_, err := s.DB.ExecContext(ctx, `
			INSERT INTO questtemplatestep (
				template_id, title, description, sort_order, progress_min, progress_max,
				check_command, check_interval_seconds
			) VALUES (?, ?, ?, ?, ?, ?, ?, ?)`,
			tid, title, asStringDef(m["description"], ""), ord, pmin, pmax,
			nullStr(asStringPtr(m["check_command"])), nullInt(asIntPtr(m["check_interval_seconds"])),
		)
		if err != nil {
			return err
		}
	}
	return nil
}

func (s *Store) loadTemplateStepsRead(ctx context.Context, tid int64) ([]map[string]any, error) {
	rows, err := s.DB.QueryContext(ctx, `
		SELECT id, template_id, title, description, sort_order, progress_min, progress_max,
			check_command, check_interval_seconds
		FROM questtemplatestep WHERE template_id=? ORDER BY sort_order, id`, tid)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := make([]map[string]any, 0)
	for rows.Next() {
		var id, tmplID int64
		var title, desc string
		var sortOrder, pmin, pmax int
		var cmd sql.NullString
		var iv sql.NullInt64
		if err := rows.Scan(&id, &tmplID, &title, &desc, &sortOrder, &pmin, &pmax, &cmd, &iv); err != nil {
			return nil, err
		}
		m := map[string]any{
			"id": id, "template_id": tmplID, "title": title, "description": desc,
			"sort_order": sortOrder, "progress_min": pmin, "progress_max": pmax,
			"check_command": nil, "check_interval_seconds": nil,
		}
		if cmd.Valid {
			m["check_command"] = cmd.String
		}
		if iv.Valid {
			m["check_interval_seconds"] = int(iv.Int64)
		}
		out = append(out, m)
	}
	return out, rows.Err()
}

func scanTemplate(row rowScanner) (TemplateRead, error) {
	var id int64
	var title, desc, freq, weekdays, tz, sig, emitMode string
	var pinned, enabled, sortOrder int
	var dur sql.NullInt64
	var deadline, ewStart, ewEnd, reward sql.NullString
	var emitChance float64
	var catID, lineID sql.NullInt64
	var created, updated sql.NullString
	var cSlug, cLabel, cColor sql.NullString
	var lTitle, lColor, lIcon, lCustom, lUpdated sql.NullString
	var lID sql.NullInt64
	err := row.Scan(
		&id, &title, &desc, &pinned, &sortOrder, &dur, &freq, &weekdays,
		&enabled, &tz, &deadline, &sig, &emitMode, &emitChance,
		&ewStart, &ewEnd, &reward, &catID, &lineID,
		&created, &updated,
		&cSlug, &cLabel, &cColor, &lTitle, &lColor, &lIcon, &lCustom, &lUpdated, &lID,
	)
	if err != nil {
		return nil, err
	}
	tr := TemplateRead{
		"id": id, "title": title, "description": desc, "pinned": pinned != 0, "sort_order": sortOrder,
		"freq": freq, "weekdays": weekdays, "enabled": enabled != 0, "timezone": tz,
		"significance": sig, "emit_mode": emitMode, "emit_chance": emitChance,
		"duration_seconds": nil, "deadline_time": nil, "emit_window_start": nil, "emit_window_end": nil,
		"reward_attrs": nil, "category_id": nil, "questline_id": nil,
		"category_slug": nil, "category_label": nil, "category_color": nil,
		"questline_title": nil, "questline_color": nil, "questline_icon": nil, "questline_icon_url": nil,
	}
	if dur.Valid {
		tr["duration_seconds"] = int(dur.Int64)
	}
	if deadline.Valid {
		tr["deadline_time"] = deadline.String
	}
	if ewStart.Valid {
		tr["emit_window_start"] = ewStart.String
	}
	if ewEnd.Valid {
		tr["emit_window_end"] = ewEnd.String
	}
	if reward.Valid {
		tr["reward_attrs"] = reward.String
	}
	if catID.Valid {
		tr["category_id"] = catID.Int64
	}
	if lineID.Valid {
		tr["questline_id"] = lineID.Int64
	}
	if created.Valid {
		if t, e := timeutil.ParseFlexible(created.String); e == nil {
			tr["created_at"] = derefISO(&t)
		}
	}
	if updated.Valid {
		if t, e := timeutil.ParseFlexible(updated.String); e == nil {
			tr["updated_at"] = derefISO(&t)
		}
	}
	if cSlug.Valid {
		tr["category_slug"] = cSlug.String
	}
	if cLabel.Valid {
		tr["category_label"] = cLabel.String
	}
	if cColor.Valid {
		tr["category_color"] = cColor.String
	}
	if lTitle.Valid {
		tr["questline_title"] = lTitle.String
	}
	if lColor.Valid {
		tr["questline_color"] = lColor.String
	}
	if lIcon.Valid {
		tr["questline_icon"] = lIcon.String
	}
	if lCustom.Valid && lCustom.String != "" && lID.Valid {
		u := "/api/questlines/" + itoa64(lID.Int64) + "/icon"
		if lUpdated.Valid {
			if t, e := timeutil.ParseFlexible(lUpdated.String); e == nil {
				if iso := timeutil.ToUTCISO(&t); iso != nil {
					u += "?v=" + *iso
				}
			}
		}
		tr["questline_icon_url"] = u
	}
	return tr, nil
}

type badInput string

func (e badInput) Error() string { return string(e) }
func errBad(s string) error      { return badInput(s) }

func asString(v any) (string, bool) {
	s, ok := v.(string)
	return s, ok
}
func asStringDef(v any, def string) string {
	if s, ok := v.(string); ok {
		return s
	}
	return def
}
func asStringPtr(v any) *string {
	if v == nil {
		return nil
	}
	if s, ok := v.(string); ok {
		return &s
	}
	return nil
}
func asBool(v any, def bool) bool {
	switch t := v.(type) {
	case bool:
		return t
	case float64:
		return t != 0
	default:
		return def
	}
}
func asInt(v any, def int) int {
	switch t := v.(type) {
	case float64:
		return int(t)
	case int:
		return t
	case int64:
		return int(t)
	default:
		return def
	}
}
func asIntPtr(v any) *int {
	if v == nil {
		return nil
	}
	n := asInt(v, 0)
	return &n
}
func asI64Ptr(v any) *int64 {
	if v == nil {
		return nil
	}
	n := int64(asInt(v, 0))
	return &n
}
func asFloat(v any, def float64) float64 {
	switch t := v.(type) {
	case float64:
		return t
	case int:
		return float64(t)
	default:
		return def
	}
}
func itoa64(n int64) string {
	return strconv.FormatInt(n, 10)
}
