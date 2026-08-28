package httpapi

import (
	"encoding/json"
	"errors"
	"net/http"
	"strconv"
	"strings"
	"time"

	"github.com/valirum/quests/go/internal/domain"
	"github.com/valirum/quests/go/internal/events"
	"github.com/valirum/quests/go/internal/health"
	"github.com/valirum/quests/go/internal/store"
	"github.com/valirum/quests/go/internal/timeutil"
)

type Server struct {
	Store   *store.Store
	Health  *health.Registry
	Hub     *events.Hub
	CORS    []string
	DataDir string
	Root    string
	// SelfBase is this server's own loopback URL (http://127.0.0.1:PORT) —
	// used by the LLM action-batch assistant to call the same HTTP API the
	// frontend/CLI use, in-process, regardless of what host QUESTS_HOST binds.
	SelfBase string
}

func (s *Server) Handler() http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("GET /api/health", s.getHealth)
	mux.HandleFunc("POST /api/health/heartbeat", s.postHeartbeat)
	mux.HandleFunc("GET /api/categories", s.listCategories)
	mux.HandleFunc("GET /api/sync", s.getSync)
	mux.HandleFunc("GET /api/events", s.getEvents)
	mux.HandleFunc("POST /api/ui/focus-quest", s.postFocusQuest)
	mux.HandleFunc("GET /ws", s.wsEvents)
	mux.HandleFunc("GET /api/quests", s.listQuests)
	mux.HandleFunc("POST /api/quests", s.createQuest)
	mux.HandleFunc("GET /api/quests/{id}", s.getQuest)
	mux.HandleFunc("PATCH /api/quests/{id}", s.patchQuest)
	mux.HandleFunc("DELETE /api/quests/{id}", s.deleteQuest)
	mux.HandleFunc("POST /api/quests/{id}/steps", s.addStep)
	mux.HandleFunc("PATCH /api/quests/{id}/steps/{step_id}", s.patchStep)
	mux.HandleFunc("DELETE /api/quests/{id}/steps/{step_id}", s.deleteStep)
	s.registerParity(mux)
	s.registerLLMActions(mux)
	s.mountSPA(mux)
	return s.cors(mux)
}

func (s *Server) cors(next http.Handler) http.Handler {
	allowed := map[string]bool{}
	for _, o := range s.CORS {
		allowed[o] = true
	}
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		origin := r.Header.Get("Origin")
		if origin != "" && allowed[origin] {
			w.Header().Set("Access-Control-Allow-Origin", origin)
			w.Header().Set("Access-Control-Allow-Methods", "GET,POST,PATCH,DELETE,OPTIONS")
			w.Header().Set("Access-Control-Allow-Headers", "Content-Type")
		}
		if r.Method == http.MethodOptions {
			w.WriteHeader(http.StatusNoContent)
			return
		}
		next.ServeHTTP(w, r)
	})
}

func writeJSON(w http.ResponseWriter, status int, v any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	enc := json.NewEncoder(w)
	enc.SetEscapeHTML(false)
	_ = enc.Encode(v)
}

func writeErr(w http.ResponseWriter, status int, detail string) {
	writeJSON(w, status, map[string]string{"detail": detail})
}

func (s *Server) getHealth(w http.ResponseWriter, r *http.Request) {
	comps := s.Health.Snapshot()
	overall := "ok"
	for _, c := range comps {
		m, _ := c.(map[string]any)
		if m["status"] != "ok" {
			overall = "degraded"
			break
		}
	}
	writeJSON(w, http.StatusOK, map[string]any{
		"status":              overall,
		"api":                 map[string]string{"status": "ok"},
		"components":          comps,
		"stale_after_seconds": health.StaleAfter,
	})
}

func (s *Server) postHeartbeat(w http.ResponseWriter, r *http.Request) {
	var body struct {
		Component string `json:"component"`
		Detail    string `json:"detail"`
	}
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
		writeErr(w, http.StatusBadRequest, "invalid JSON")
		return
	}
	if body.Component != "overlay" && body.Component != "telegram" {
		writeErr(w, http.StatusBadRequest, "component must be overlay or telegram")
		return
	}
	s.Health.Record(body.Component, body.Detail)
	writeJSON(w, http.StatusOK, map[string]string{"status": "ok", "component": body.Component})
}

func (s *Server) listCategories(w http.ResponseWriter, r *http.Request) {
	rows, err := s.Store.ListCategories(r.Context())
	if err != nil {
		writeErr(w, http.StatusInternalServerError, err.Error())
		return
	}
	if rows == nil {
		rows = []domain.Category{}
	}
	writeJSON(w, http.StatusOK, rows)
}

func (s *Server) listQuests(w http.ResponseWriter, r *http.Request) {
	var f store.ListFilter
	if st := r.URL.Query().Get("status"); st != "" {
		s := domain.QuestStatus(st)
		f.Status = &s
	}
	if p := r.URL.Query().Get("pinned"); p != "" {
		v := p == "1" || strings.EqualFold(p, "true")
		f.Pinned = &v
	}
	if ql := r.URL.Query().Get("questline_id"); ql != "" {
		if n, err := strconv.ParseInt(ql, 10, 64); err == nil {
			f.QuestlineID = &n
		}
	}
	quests, err := s.Store.ListQuests(r.Context(), f)
	if err != nil {
		writeErr(w, http.StatusInternalServerError, err.Error())
		return
	}
	now := timeutil.NowUTC()
	out := make([]domain.QuestRead, 0, len(quests))
	for _, q := range quests {
		out = append(out, domain.ToQuestRead(q, now))
	}
	writeJSON(w, http.StatusOK, out)
}

func (s *Server) getQuest(w http.ResponseWriter, r *http.Request) {
	id, err := strconv.ParseInt(r.PathValue("id"), 10, 64)
	if err != nil {
		writeErr(w, http.StatusBadRequest, "invalid id")
		return
	}
	q, err := s.Store.GetQuest(r.Context(), id)
	if errors.Is(err, store.ErrNotFound) {
		writeErr(w, http.StatusNotFound, "Quest not found")
		return
	}
	if err != nil {
		writeErr(w, http.StatusInternalServerError, err.Error())
		return
	}
	writeJSON(w, http.StatusOK, domain.ToQuestRead(q, timeutil.NowUTC()))
}

func (s *Server) createQuest(w http.ResponseWriter, r *http.Request) {
	var body domain.QuestCreate
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
		writeErr(w, http.StatusBadRequest, "invalid JSON")
		return
	}
	body.Title = strings.TrimSpace(body.Title)
	if body.Title == "" {
		writeErr(w, http.StatusUnprocessableEntity, "title required")
		return
	}
	if body.Status == "" {
		body.Status = domain.StatusActive
	}
	if body.Significance == "" {
		body.Significance = domain.SigCommon
	}
	now := timeutil.NowUTC()
	var deadline *time.Time
	if body.DeadlineAt != nil && strings.TrimSpace(*body.DeadlineAt) != "" {
		t, err := timeutil.ParseFlexible(*body.DeadlineAt)
		if err != nil {
			writeErr(w, http.StatusUnprocessableEntity, "invalid deadline_at")
			return
		}
		deadline = &t
	}
	d, dur := timeutil.NormalizeDeadline(deadline, body.DurationSeconds, body.DurationSeconds != nil, now)
	catID, err := store.ValidateCategoryID(r.Context(), s.Store, body.CategoryID)
	if err != nil {
		writeErr(w, http.StatusInternalServerError, err.Error())
		return
	}
	lineID := body.QuestlineID
	if lineID != nil {
		ok, err := s.Store.QuestlineExists(r.Context(), *lineID)
		if err != nil {
			writeErr(w, http.StatusInternalServerError, err.Error())
			return
		}
		if !ok {
			writeErr(w, http.StatusUnprocessableEntity, "questline not found")
			return
		}
		if c, err := s.Store.QuestlineCategory(r.Context(), *lineID); err == nil && c != nil {
			catID = c
		}
	}
	q := domain.Quest{
		Title:           body.Title,
		Description:     body.Description,
		Status:          body.Status,
		Significance:    body.Significance,
		Pinned:          body.Pinned,
		SortOrder:       body.SortOrder,
		DeadlineAt:      d,
		DurationSeconds: dur,
		RewardAttrs:     body.RewardAttrs,
		CategoryID:      catID,
		QuestlineID:     lineID,
		CreatedAt:       now,
		UpdatedAt:       now,
	}
	if len(body.Steps) == 0 {
		q.Steps = []domain.Step{{Title: body.Title, ProgressTotal: 1, SortOrder: 0}}
	} else {
		for i, sc := range body.Steps {
			ord := i
			if sc.SortOrder != nil {
				ord = *sc.SortOrder
			}
			cmd, iv := store.NormalizeCheck(sc.CheckCommand, sc.CheckIntervalSeconds)
			st := domain.Step{
				Title: sc.Title, Description: sc.Description,
				ProgressCurrent: sc.ProgressCurrent, ProgressTotal: sc.ProgressTotal,
				SortOrder: ord, CheckCommand: cmd, CheckIntervalSeconds: iv,
			}
			if st.ProgressTotal < 1 {
				st.ProgressTotal = 1
			}
			q.Steps = append(q.Steps, st)
		}
	}
	created, err := s.Store.CreateQuest(r.Context(), q)
	if err != nil {
		writeErr(w, http.StatusInternalServerError, err.Error())
		return
	}
	quiet, source := s.publishOpts(r)
	qid := created.ID
	s.Hub.Publish("quest_created", events.PublishOpts{
		QuestID: &qid, Title: created.Title, Description: created.Description,
		Detail: "создано задание", Toast: !quiet, Source: source,
		Significance: string(created.Significance),
	})
	writeJSON(w, http.StatusCreated, domain.ToQuestRead(created, timeutil.NowUTC()))
}

func (s *Server) patchQuest(w http.ResponseWriter, r *http.Request) {
	id, err := strconv.ParseInt(r.PathValue("id"), 10, 64)
	if err != nil {
		writeErr(w, http.StatusBadRequest, "invalid id")
		return
	}
	var raw map[string]json.RawMessage
	if err := json.NewDecoder(r.Body).Decode(&raw); err != nil {
		writeErr(w, http.StatusBadRequest, "invalid JSON")
		return
	}
	if _, ok := raw["steps"]; ok {
		writeErr(w, http.StatusUnprocessableEntity, "steps replace removed; use step CRUD")
		return
	}
	q, err := s.Store.GetQuest(r.Context(), id)
	if errors.Is(err, store.ErrNotFound) {
		writeErr(w, http.StatusNotFound, "Quest not found")
		return
	}
	if err != nil {
		writeErr(w, http.StatusInternalServerError, err.Error())
		return
	}
	beforeStatus := q.Status
	deadlineTouched := false
	durationExplicit := false
	if v, ok := raw["title"]; ok {
		_ = json.Unmarshal(v, &q.Title)
	}
	if v, ok := raw["description"]; ok {
		_ = json.Unmarshal(v, &q.Description)
	}
	if v, ok := raw["status"]; ok {
		var st domain.QuestStatus
		_ = json.Unmarshal(v, &st)
		q.Status = st
	}
	if v, ok := raw["significance"]; ok {
		var sg domain.Significance
		_ = json.Unmarshal(v, &sg)
		q.Significance = sg
	}
	if v, ok := raw["pinned"]; ok {
		_ = json.Unmarshal(v, &q.Pinned)
	}
	if v, ok := raw["sort_order"]; ok {
		_ = json.Unmarshal(v, &q.SortOrder)
	}
	if v, ok := raw["reward_attrs"]; ok {
		var s *string
		_ = json.Unmarshal(v, &s)
		q.RewardAttrs = s
	}
	if v, ok := raw["category_id"]; ok {
		var cid *int64
		_ = json.Unmarshal(v, &cid)
		cid, err = store.ValidateCategoryID(r.Context(), s.Store, cid)
		if err != nil {
			writeErr(w, http.StatusInternalServerError, err.Error())
			return
		}
		q.CategoryID = cid
	}
	if v, ok := raw["questline_id"]; ok {
		var lid *int64
		_ = json.Unmarshal(v, &lid)
		q.QuestlineID = lid
		if lid != nil {
			if c, err := s.Store.QuestlineCategory(r.Context(), *lid); err == nil && c != nil {
				q.CategoryID = c
			}
		}
	}
	if v, ok := raw["deadline_at"]; ok {
		deadlineTouched = true
		if string(v) == "null" {
			q.DeadlineAt = nil
		} else {
			var s string
			if err := json.Unmarshal(v, &s); err == nil {
				t, err := timeutil.ParseFlexible(s)
				if err != nil {
					writeErr(w, http.StatusUnprocessableEntity, "invalid deadline_at")
					return
				}
				q.DeadlineAt = &t
			}
		}
	}
	if v, ok := raw["duration_seconds"]; ok {
		durationExplicit = true
		if string(v) == "null" {
			q.DurationSeconds = nil
		} else {
			var n int
			_ = json.Unmarshal(v, &n)
			q.DurationSeconds = &n
		}
	}
	now := timeutil.NowUTC()
	q.UpdatedAt = now
	if q.Status == domain.StatusCompleted && q.CompletedAt == nil {
		q.CompletedAt = &now
	}
	if q.Status != domain.StatusCompleted {
		q.CompletedAt = nil
	}
	if deadlineTouched || durationExplicit || (q.DeadlineAt != nil && q.DurationSeconds == nil) {
		d, dur := timeutil.NormalizeDeadline(q.DeadlineAt, q.DurationSeconds, durationExplicit, now)
		q.DeadlineAt = d
		q.DurationSeconds = dur
	}
	kind := "quest_updated"
	detail := "изменено"
	toast := false
	if q.Status != beforeStatus {
		switch q.Status {
		case domain.StatusCompleted:
			kind, detail, toast = "quest_completed", "завершено", true
		case domain.StatusFailed:
			kind, detail, toast = "quest_failed", "провалено", true
		case domain.StatusDelayed:
			kind, detail, toast = "quest_delayed", "просрочено", true
		default:
			kind, detail, toast = "status_changed", string(beforeStatus)+" → "+string(q.Status), true
		}
	}
	updated, err := s.Store.UpdateQuest(r.Context(), q, kind, detail)
	if err != nil {
		writeErr(w, http.StatusInternalServerError, err.Error())
		return
	}
	if updated.Status != beforeStatus {
		_ = s.Store.ApplyQuestStatusRewards(r.Context(), updated, updated.Status)
	}
	quiet, source := s.publishOpts(r)
	qid := updated.ID
	s.Hub.Publish(kind, events.PublishOpts{
		QuestID: &qid, Title: updated.Title, Description: updated.Description,
		Detail: detail, Toast: !quiet && toast, Source: source,
		Significance: string(updated.Significance),
	})
	writeJSON(w, http.StatusOK, domain.ToQuestRead(updated, timeutil.NowUTC()))
}

func (s *Server) deleteQuest(w http.ResponseWriter, r *http.Request) {
	id, err := strconv.ParseInt(r.PathValue("id"), 10, 64)
	if err != nil {
		writeErr(w, http.StatusBadRequest, "invalid id")
		return
	}
	q, err := s.Store.GetQuest(r.Context(), id)
	if errors.Is(err, store.ErrNotFound) {
		writeErr(w, http.StatusNotFound, "Quest not found")
		return
	}
	if err != nil {
		writeErr(w, http.StatusInternalServerError, err.Error())
		return
	}
	if err := s.Store.DeleteQuest(r.Context(), id, q.Title); err != nil {
		writeErr(w, http.StatusInternalServerError, err.Error())
		return
	}
	quiet, source := s.publishOpts(r)
	s.Hub.Publish("quest_deleted", events.PublishOpts{
		QuestID: &id, Title: q.Title, Description: q.Description,
		Detail: "удалено", Toast: !quiet, Source: source,
	})
	w.WriteHeader(http.StatusNoContent)
}

func (s *Server) addStep(w http.ResponseWriter, r *http.Request) {
	qid, err := strconv.ParseInt(r.PathValue("id"), 10, 64)
	if err != nil {
		writeErr(w, http.StatusBadRequest, "invalid id")
		return
	}
	var body domain.StepCreate
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
		writeErr(w, http.StatusBadRequest, "invalid JSON")
		return
	}
	q, err := s.Store.GetQuest(r.Context(), qid)
	if errors.Is(err, store.ErrNotFound) {
		writeErr(w, http.StatusNotFound, "Quest not found")
		return
	}
	if err != nil {
		writeErr(w, http.StatusInternalServerError, err.Error())
		return
	}
	ord := 0
	if body.SortOrder != nil {
		ord = *body.SortOrder
	} else if len(q.Steps) > 0 {
		for _, st := range q.Steps {
			if st.SortOrder >= ord {
				ord = st.SortOrder + 1
			}
		}
	}
	cmd, iv := store.NormalizeCheck(body.CheckCommand, body.CheckIntervalSeconds)
	st := domain.Step{
		QuestID: qid, Title: strings.TrimSpace(body.Title), Description: body.Description,
		ProgressCurrent: body.ProgressCurrent, ProgressTotal: body.ProgressTotal,
		SortOrder: ord, CheckCommand: cmd, CheckIntervalSeconds: iv,
	}
	if st.Title == "" {
		writeErr(w, http.StatusUnprocessableEntity, "title required")
		return
	}
	if st.ProgressTotal < 1 {
		st.ProgressTotal = 1
	}
	q.Steps = append(q.Steps, st)
	now := timeutil.NowUTC()
	domain.SyncStatusFromSteps(&q, now)
	q.UpdatedAt = now
	updated, err := s.Store.AddStep(r.Context(), qid, st, q)
	if err != nil {
		writeErr(w, http.StatusInternalServerError, err.Error())
		return
	}
	quiet, source := s.publishOpts(r)
	id := updated.ID
	_ = quiet
	s.Hub.Publish("quest_updated", events.PublishOpts{
		QuestID: &id, Title: updated.Title, Detail: "+шаги: 1",
		Toast: false, Source: source, Significance: string(updated.Significance),
	})
	writeJSON(w, http.StatusCreated, domain.ToQuestRead(updated, timeutil.NowUTC()))
}

func (s *Server) patchStep(w http.ResponseWriter, r *http.Request) {
	qid, _ := strconv.ParseInt(r.PathValue("id"), 10, 64)
	sid, _ := strconv.ParseInt(r.PathValue("step_id"), 10, 64)
	var body domain.StepUpdate
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
		writeErr(w, http.StatusBadRequest, "invalid JSON")
		return
	}
	q, err := s.Store.GetQuest(r.Context(), qid)
	if errors.Is(err, store.ErrNotFound) {
		writeErr(w, http.StatusNotFound, "Quest not found")
		return
	}
	if err != nil {
		writeErr(w, http.StatusInternalServerError, err.Error())
		return
	}
	var st *domain.Step
	for i := range q.Steps {
		if q.Steps[i].ID == sid {
			st = &q.Steps[i]
			break
		}
	}
	if st == nil {
		writeErr(w, http.StatusNotFound, "Step not found")
		return
	}
	if body.Title != nil {
		st.Title = *body.Title
	}
	if body.Description != nil {
		st.Description = *body.Description
	}
	if body.ProgressCurrent != nil {
		st.ProgressCurrent = *body.ProgressCurrent
	}
	if body.ProgressTotal != nil {
		st.ProgressTotal = *body.ProgressTotal
	}
	if body.SortOrder != nil {
		st.SortOrder = *body.SortOrder
	}
	if body.CheckCommand != nil || body.CheckIntervalSeconds != nil {
		cmd := st.CheckCommand
		iv := st.CheckIntervalSeconds
		if body.CheckCommand != nil {
			cmd = body.CheckCommand
		}
		if body.CheckIntervalSeconds != nil {
			iv = body.CheckIntervalSeconds
		}
		st.CheckCommand, st.CheckIntervalSeconds = store.NormalizeCheck(cmd, iv)
	}
	domain.ClampStep(st)
	now := timeutil.NowUTC()
	domain.SyncStatusFromSteps(&q, now)
	q.UpdatedAt = now
	kind := "quest_updated"
	detail := "изменено"
	if st.Done {
		kind = "step_completed"
		detail = st.Title
	}
	updated, err := s.Store.UpdateStep(r.Context(), *st, q, kind, detail)
	if err != nil {
		writeErr(w, http.StatusInternalServerError, err.Error())
		return
	}
	quiet, source := s.publishOpts(r)
	id := updated.ID
	toast := kind == "step_completed" || kind == "quest_completed"
	s.Hub.Publish(kind, events.PublishOpts{
		QuestID: &id, Title: updated.Title, Detail: detail,
		Toast: !quiet && toast, Source: source, Significance: string(updated.Significance),
		StepTitle: st.Title,
	})
	writeJSON(w, http.StatusOK, domain.ToQuestRead(updated, timeutil.NowUTC()))
}

func (s *Server) deleteStep(w http.ResponseWriter, r *http.Request) {
	qid, _ := strconv.ParseInt(r.PathValue("id"), 10, 64)
	sid, _ := strconv.ParseInt(r.PathValue("step_id"), 10, 64)
	q, err := s.Store.GetQuest(r.Context(), qid)
	if errors.Is(err, store.ErrNotFound) {
		writeErr(w, http.StatusNotFound, "Quest not found")
		return
	}
	if err != nil {
		writeErr(w, http.StatusInternalServerError, err.Error())
		return
	}
	if len(q.Steps) <= 1 {
		writeErr(w, http.StatusBadRequest, "Cannot delete the last step")
		return
	}
	found := false
	var next []domain.Step
	for _, st := range q.Steps {
		if st.ID == sid {
			found = true
			continue
		}
		next = append(next, st)
	}
	if !found {
		writeErr(w, http.StatusNotFound, "Step not found")
		return
	}
	q.Steps = next
	now := timeutil.NowUTC()
	domain.SyncStatusFromSteps(&q, now)
	q.UpdatedAt = now
	updated, err := s.Store.DeleteStep(r.Context(), qid, sid, q)
	if errors.Is(err, store.ErrNotFound) {
		writeErr(w, http.StatusNotFound, "Step not found")
		return
	}
	if err != nil {
		writeErr(w, http.StatusInternalServerError, err.Error())
		return
	}
	quiet, source := s.publishOpts(r)
	id := updated.ID
	_ = quiet
	s.Hub.Publish("quest_updated", events.PublishOpts{
		QuestID: &id, Title: updated.Title, Detail: "−шаги: 1",
		Toast: false, Source: source, Significance: string(updated.Significance),
	})
	writeJSON(w, http.StatusOK, domain.ToQuestRead(updated, timeutil.NowUTC()))
}
