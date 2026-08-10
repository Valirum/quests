package store

import (
	"context"
	"database/sql"
	"encoding/json"
	"math"
	"time"

	"github.com/valirum/quests/go/internal/domain"
	"github.com/valirum/quests/go/internal/timeutil"
)

const (
	momentumMin     = 0
	momentumMax     = 100
	momentumDefault = 50
	xpOnComplete    = 20
	momentumOnComplete = 12
	momentumOnFail     = -20
	momentumOnDelayed  = -2
	attrProgressPool   = 10
)

var attrOrder = []string{"str", "dex", "con", "int", "wis", "cha"}
var attrLabelRU = map[string]string{
	"str": "Сила", "dex": "Ловкость", "con": "Выносливость",
	"int": "Интеллект", "wis": "Мудрость", "cha": "Харизма",
}
var sigMult = map[string]float64{
	"common": 1, "uncommon": 1.25, "epic": 1.75, "legendary": 2.5,
}

func progressToNext(rank int) int {
	return 10 + rank*5
}

func (s *Store) EnsureHero(ctx context.Context) error {
	var id int64
	err := s.DB.QueryRowContext(ctx, `SELECT id FROM herosheet WHERE id=1`).Scan(&id)
	if err == nil {
		return nil
	}
	if err != sql.ErrNoRows {
		return err
	}
	now := timeutil.ToDBUTC(timeutil.NowUTC())
	_, err = s.DB.ExecContext(ctx, `
		INSERT INTO herosheet (id, xp, momentum, momentum_updated_at, updated_at)
		VALUES (1, 0, ?, ?, ?)`, momentumDefault, now, now)
	return err
}

func (s *Store) DecayMomentum(ctx context.Context) error {
	if err := s.EnsureHero(ctx); err != nil {
		return err
	}
	var xp, mom int
	var momAt, updated sql.NullString
	err := s.DB.QueryRowContext(ctx, `
		SELECT xp, momentum, momentum_updated_at, updated_at FROM herosheet WHERE id=1`).Scan(&xp, &mom, &momAt, &updated)
	if err != nil {
		return err
	}
	if !momAt.Valid || mom <= 0 {
		return nil
	}
	updatedAt, err := timeutil.ParseFlexible(momAt.String)
	if err != nil {
		return err
	}
	now := timeutil.NowUTC()
	hours := int(now.Sub(updatedAt).Hours())
	if hours <= 0 {
		return nil
	}
	delta := -min(hours, mom)
	if delta == 0 {
		return nil
	}
	newMom := clampMom(mom + delta)
	newMomAt := updatedAt.Add(time.Duration(hours) * time.Hour)
	_, err = s.DB.ExecContext(ctx, `
		UPDATE herosheet SET momentum=?, momentum_updated_at=?, updated_at=? WHERE id=1`,
		newMom, timeutil.ToDBUTC(newMomAt), timeutil.ToDBUTC(now))
	if err != nil {
		return err
	}
	_, err = s.DB.ExecContext(ctx, `
		INSERT INTO metricledger (at, kind, attr_id, delta, balance_after, quest_id, reason, flavor)
		VALUES (?, 'momentum', NULL, ?, ?, NULL, 'momentum_decay', ?)`,
		timeutil.ToDBUTC(now), delta, newMom, "Бездействие (−"+itoa(abs(delta))+"/ч)")
	return err
}

func (s *Store) GetHero(ctx context.Context) (map[string]any, error) {
	if err := s.EnsureHero(ctx); err != nil {
		return nil, err
	}
	_ = s.DecayMomentum(ctx)
	var xp, mom int
	var momAt, updated sql.NullString
	err := s.DB.QueryRowContext(ctx, `
		SELECT xp, momentum, momentum_updated_at, updated_at FROM herosheet WHERE id=1`).Scan(&xp, &mom, &momAt, &updated)
	if err != nil {
		return nil, err
	}
	attrs := make([]map[string]any, 0, len(attrOrder))
	rows, err := s.DB.QueryContext(ctx, `SELECT attr_id, rank, progress FROM heroattribute`)
	byID := map[string]struct{ rank, progress int }{}
	if err == nil {
		for rows.Next() {
			var id string
			var rank, progress int
			_ = rows.Scan(&id, &rank, &progress)
			byID[id] = struct{ rank, progress int }{rank, progress}
		}
		_ = rows.Close()
	}
	for _, id := range attrOrder {
		a := byID[id]
		attrs = append(attrs, map[string]any{
			"attr_id": id, "label": attrLabelRU[id],
			"rank": a.rank, "progress": a.progress, "progress_to_next": progressToNext(a.rank),
		})
	}
	recent := make([]map[string]any, 0)
	rrows, err := s.DB.QueryContext(ctx, `
		SELECT id, at, kind, attr_id, delta, balance_after, quest_id, reason, flavor
		FROM metricledger ORDER BY at DESC, id DESC LIMIT 30`)
	if err == nil {
		for rrows.Next() {
			var id int64
			var at, kind, reason string
			var flavor sql.NullString
			var attr sql.NullString
			var delta, bal int
			var qid sql.NullInt64
			_ = rrows.Scan(&id, &at, &kind, &attr, &delta, &bal, &qid, &reason, &flavor)
			t, _ := timeutil.ParseFlexible(at)
			m := map[string]any{
				"id": id, "at": derefISO(&t), "kind": kind, "attr_id": nil,
				"delta": delta, "balance_after": bal, "quest_id": nil, "reason": reason, "flavor": nil,
			}
			if attr.Valid {
				m["attr_id"] = attr.String
			}
			if qid.Valid {
				m["quest_id"] = qid.Int64
			}
			if flavor.Valid {
				m["flavor"] = flavor.String
			}
			recent = append(recent, m)
		}
		_ = rrows.Close()
	}
	out := map[string]any{
		"xp": xp, "momentum": mom, "attributes": attrs, "recent": recent,
	}
	if momAt.Valid {
		t, _ := timeutil.ParseFlexible(momAt.String)
		out["momentum_updated_at"] = derefISO(&t)
	}
	if updated.Valid {
		t, _ := timeutil.ParseFlexible(updated.String)
		out["updated_at"] = derefISO(&t)
	}
	return out, nil
}

func (s *Store) ApplyQuestStatusRewards(ctx context.Context, q domain.Quest, newStatus domain.QuestStatus) error {
	if q.ID == 0 {
		return nil
	}
	var reason string
	switch newStatus {
	case domain.StatusCompleted:
		reason = "quest_completed"
	case domain.StatusFailed:
		reason = "quest_failed"
	case domain.StatusDelayed:
		reason = "quest_delayed"
	default:
		return nil
	}
	var n int
	err := s.DB.QueryRowContext(ctx, `
		SELECT 1 FROM metricledger WHERE quest_id=? AND reason=? LIMIT 1`, q.ID, reason).Scan(&n)
	if err == nil {
		return nil // already applied
	}
	if err != sql.ErrNoRows {
		return err
	}
	if err := s.EnsureHero(ctx); err != nil {
		return err
	}
	mult := sigMult[string(q.Significance)]
	if mult == 0 {
		mult = 1
	}
	now := timeutil.NowUTC()
	title := q.Title

	var xp, mom int
	var momAt sql.NullString
	_ = s.DB.QueryRowContext(ctx, `SELECT xp, momentum, momentum_updated_at FROM herosheet WHERE id=1`).Scan(&xp, &mom, &momAt)

	switch newStatus {
	case domain.StatusCompleted:
		dxp := max(1, int(math.Round(float64(xpOnComplete)*mult)))
		dm := max(1, int(math.Round(float64(momentumOnComplete)*mult)))
		xp += dxp
		mom = clampMom(mom + dm)
		_, _ = s.DB.ExecContext(ctx, `UPDATE herosheet SET xp=?, momentum=?, momentum_updated_at=?, updated_at=? WHERE id=1`,
			xp, mom, timeutil.ToDBUTC(now), timeutil.ToDBUTC(now))
		_, _ = s.DB.ExecContext(ctx, `
			INSERT INTO metricledger (at, kind, attr_id, delta, balance_after, quest_id, reason, flavor)
			VALUES (?, 'xp', NULL, ?, ?, ?, ?, ?)`,
			timeutil.ToDBUTC(now), dxp, xp, q.ID, reason, "+"+itoa(dxp)+" XP · "+title)
		_, _ = s.DB.ExecContext(ctx, `
			INSERT INTO metricledger (at, kind, attr_id, delta, balance_after, quest_id, reason, flavor)
			VALUES (?, 'momentum', NULL, ?, ?, ?, ?, ?)`,
			timeutil.ToDBUTC(now), dm, mom, q.ID, reason+":momentum", "Импульс +"+itoa(dm))
		_ = s.applyAttrPool(ctx, q, int(math.Round(float64(attrProgressPool)*mult)), reason, title, now)
	case domain.StatusFailed:
		dm := min(-1, int(math.Round(float64(momentumOnFail)*mult)))
		mom = clampMom(mom + dm)
		_, _ = s.DB.ExecContext(ctx, `UPDATE herosheet SET momentum=?, momentum_updated_at=?, updated_at=? WHERE id=1`,
			mom, timeutil.ToDBUTC(now), timeutil.ToDBUTC(now))
		_, _ = s.DB.ExecContext(ctx, `
			INSERT INTO metricledger (at, kind, attr_id, delta, balance_after, quest_id, reason, flavor)
			VALUES (?, 'momentum', NULL, ?, ?, ?, ?, ?)`,
			timeutil.ToDBUTC(now), dm, mom, q.ID, reason, "Импульс "+itoa(dm)+" · провал: "+title)
	case domain.StatusDelayed:
		dm := momentumOnDelayed
		mom = clampMom(mom + dm)
		_, _ = s.DB.ExecContext(ctx, `UPDATE herosheet SET momentum=?, momentum_updated_at=?, updated_at=? WHERE id=1`,
			mom, timeutil.ToDBUTC(now), timeutil.ToDBUTC(now))
		_, _ = s.DB.ExecContext(ctx, `
			INSERT INTO metricledger (at, kind, attr_id, delta, balance_after, quest_id, reason, flavor)
			VALUES (?, 'momentum', NULL, ?, ?, ?, ?, ?)`,
			timeutil.ToDBUTC(now), dm, mom, q.ID, reason, "Импульс "+itoa(dm)+" · отсрочка: "+title)
	}
	return nil
}

func (s *Store) applyAttrPool(ctx context.Context, q domain.Quest, pool int, reason, title string, now time.Time) error {
	weights := map[string]int{}
	if q.RewardAttrs != nil && *q.RewardAttrs != "" {
		_ = json.Unmarshal([]byte(*q.RewardAttrs), &weights)
	}
	if len(weights) == 0 {
		return nil
	}
	totalW := 0
	for _, w := range weights {
		if w > 0 {
			totalW += w
		}
	}
	if totalW == 0 || pool < 1 {
		return nil
	}
	for attrID, w := range weights {
		if w <= 0 {
			continue
		}
		gain := max(1, pool*w/totalW)
		var rank, progress int
		err := s.DB.QueryRowContext(ctx, `SELECT rank, progress FROM heroattribute WHERE attr_id=?`, attrID).Scan(&rank, &progress)
		if err == sql.ErrNoRows {
			_, _ = s.DB.ExecContext(ctx, `INSERT INTO heroattribute (attr_id, rank, progress, updated_at) VALUES (?,0,0,?)`, attrID, timeutil.ToDBUTC(now))
		} else if err != nil {
			continue
		}
		progress += gain
		for progress >= progressToNext(rank) {
			need := progressToNext(rank)
			progress -= need
			rank++
		}
		_, _ = s.DB.ExecContext(ctx, `
			INSERT INTO heroattribute (attr_id, rank, progress, updated_at) VALUES (?, ?, ?, ?)
			ON CONFLICT(attr_id) DO UPDATE SET rank=excluded.rank, progress=excluded.progress, updated_at=excluded.updated_at`,
			attrID, rank, progress, timeutil.ToDBUTC(now))
		// SQLite unique on attr_id — check schema; may need UPDATE only
		_, _ = s.DB.ExecContext(ctx, `UPDATE heroattribute SET rank=?, progress=?, updated_at=? WHERE attr_id=?`,
			rank, progress, timeutil.ToDBUTC(now), attrID)
		_, _ = s.DB.ExecContext(ctx, `
			INSERT INTO metricledger (at, kind, attr_id, delta, balance_after, quest_id, reason, flavor)
			VALUES (?, 'attr', ?, ?, ?, ?, ?, ?)`,
			timeutil.ToDBUTC(now), attrID, gain, progress, q.ID, reason+":attr:"+attrID, title)
	}
	return nil
}

func clampMom(v int) int {
	if v < momentumMin {
		return momentumMin
	}
	if v > momentumMax {
		return momentumMax
	}
	return v
}
func min(a, b int) int {
	if a < b {
		return a
	}
	return b
}
func max(a, b int) int {
	if a > b {
		return a
	}
	return b
}
func abs(a int) int {
	if a < 0 {
		return -a
	}
	return a
}
func itoa(n int) string {
	return itoa64(int64(n))
}
