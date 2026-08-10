package httpapi

import (
	"encoding/json"
	"errors"
	"io"
	"net/http"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"time"

	"github.com/valirum/quests/go/internal/domain"
	"github.com/valirum/quests/go/internal/schedule"
	"github.com/valirum/quests/go/internal/store"
	"github.com/valirum/quests/go/internal/timeutil"
)

func (s *Server) registerParity(mux *http.ServeMux) {
	mux.HandleFunc("GET /api/questlines", s.listQuestlines)
	mux.HandleFunc("POST /api/questlines", s.createQuestline)
	mux.HandleFunc("GET /api/questlines/{id}", s.getQuestline)
	mux.HandleFunc("PATCH /api/questlines/{id}", s.patchQuestline)
	mux.HandleFunc("DELETE /api/questlines/{id}", s.deleteQuestline)
	mux.HandleFunc("GET /api/questlines/{id}/icon", s.getQuestlineIcon)
	mux.HandleFunc("POST /api/questlines/{id}/icon", s.postQuestlineIcon)
	mux.HandleFunc("DELETE /api/questlines/{id}/icon", s.deleteQuestlineIcon)

	mux.HandleFunc("GET /api/templates", s.listTemplates)
	mux.HandleFunc("POST /api/templates", s.createTemplate)
	mux.HandleFunc("GET /api/templates/{id}", s.getTemplate)
	mux.HandleFunc("PATCH /api/templates/{id}", s.patchTemplate)
	mux.HandleFunc("DELETE /api/templates/{id}", s.deleteTemplate)
	mux.HandleFunc("POST /api/templates/{id}/copy", s.copyTemplate)

	mux.HandleFunc("GET /api/hero", s.getHero)
	mux.HandleFunc("GET /api/stats", s.getStats)
	mux.HandleFunc("GET /api/quest-log", s.getQuestLog)
	mux.HandleFunc("GET /api/context", s.getContext)
}

func (s *Server) listQuestlines(w http.ResponseWriter, r *http.Request) {
	rows, err := s.Store.ListQuestlines(r.Context())
	if err != nil {
		writeErr(w, 500, err.Error())
		return
	}
	writeJSON(w, 200, rows)
}

func (s *Server) getQuestline(w http.ResponseWriter, r *http.Request) {
	id, _ := strconv.ParseInt(r.PathValue("id"), 10, 64)
	row, err := s.Store.GetQuestline(r.Context(), id)
	if errors.Is(err, store.ErrNotFound) {
		writeErr(w, 404, "Questline not found")
		return
	}
	if err != nil {
		writeErr(w, 500, err.Error())
		return
	}
	writeJSON(w, 200, row)
}

func (s *Server) createQuestline(w http.ResponseWriter, r *http.Request) {
	var body map[string]any
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
		writeErr(w, 400, "invalid JSON")
		return
	}
	title, _ := body["title"].(string)
	desc, _ := body["description"].(string)
	color, _ := body["color"].(string)
	icon, _ := body["icon"].(string)
	var cat *int64
	if v, ok := body["category_id"].(float64); ok {
		i := int64(v)
		cat = &i
	}
	row, err := s.Store.CreateQuestline(r.Context(), strings.TrimSpace(title), desc, cat, color, icon)
	if err != nil {
		writeErr(w, 500, err.Error())
		return
	}
	writeJSON(w, 201, row)
}

func (s *Server) patchQuestline(w http.ResponseWriter, r *http.Request) {
	id, _ := strconv.ParseInt(r.PathValue("id"), 10, 64)
	var body map[string]any
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
		writeErr(w, 400, "invalid JSON")
		return
	}
	row, err := s.Store.UpdateQuestline(r.Context(), id, body)
	if errors.Is(err, store.ErrNotFound) {
		writeErr(w, 404, "Questline not found")
		return
	}
	if err != nil {
		writeErr(w, 500, err.Error())
		return
	}
	writeJSON(w, 200, row)
}

func (s *Server) deleteQuestline(w http.ResponseWriter, r *http.Request) {
	id, _ := strconv.ParseInt(r.PathValue("id"), 10, 64)
	if err := s.Store.DeleteQuestline(r.Context(), id, s.DataDir); err != nil {
		if errors.Is(err, store.ErrNotFound) {
			writeErr(w, 404, "Questline not found")
			return
		}
		writeErr(w, 500, err.Error())
		return
	}
	w.WriteHeader(204)
}

func questlineCustomIcon(row map[string]any) string {
	switch v := row["custom_icon"].(type) {
	case string:
		return v
	case *string:
		if v != nil {
			return *v
		}
	}
	return ""
}

func (s *Server) getQuestlineIcon(w http.ResponseWriter, r *http.Request) {
	id, _ := strconv.ParseInt(r.PathValue("id"), 10, 64)
	row, err := s.Store.GetQuestline(r.Context(), id)
	if errors.Is(err, store.ErrNotFound) {
		writeErr(w, 404, "Questline not found")
		return
	}
	custom := questlineCustomIcon(row)
	if custom == "" || !store.SafeIconName(custom) {
		writeErr(w, 404, "Icon not found")
		return
	}
	path := filepath.Join(s.DataDir, "questline-icons", custom)
	http.ServeFile(w, r, path)
}

func (s *Server) postQuestlineIcon(w http.ResponseWriter, r *http.Request) {
	id, _ := strconv.ParseInt(r.PathValue("id"), 10, 64)
	if _, err := s.Store.GetQuestline(r.Context(), id); errors.Is(err, store.ErrNotFound) {
		writeErr(w, 404, "Questline not found")
		return
	}
	if err := r.ParseMultipartForm(600 << 10); err != nil {
		writeErr(w, 400, "invalid multipart")
		return
	}
	file, hdr, err := r.FormFile("file")
	if err != nil {
		writeErr(w, 400, "file required")
		return
	}
	defer file.Close()
	raw, err := io.ReadAll(io.LimitReader(file, 512*1024+1))
	if err != nil || len(raw) == 0 || len(raw) > 512*1024 {
		writeErr(w, 400, "icon too large or empty")
		return
	}
	ct := hdr.Header.Get("Content-Type")
	ext := ".png"
	switch {
	case strings.Contains(ct, "jpeg"), strings.HasSuffix(strings.ToLower(hdr.Filename), ".jpg"), strings.HasSuffix(strings.ToLower(hdr.Filename), ".jpeg"):
		ext = ".jpg"
	case strings.Contains(ct, "webp"), strings.HasSuffix(strings.ToLower(hdr.Filename), ".webp"):
		ext = ".webp"
	case strings.Contains(ct, "gif"), strings.HasSuffix(strings.ToLower(hdr.Filename), ".gif"):
		ext = ".gif"
	case strings.Contains(ct, "svg"), strings.HasSuffix(strings.ToLower(hdr.Filename), ".svg"):
		ext = ".svg"
	}
	dir := filepath.Join(s.DataDir, "questline-icons")
	_ = os.MkdirAll(dir, 0o755)
	name := strconv.FormatInt(id, 10) + ext
	if err := os.WriteFile(filepath.Join(dir, name), raw, 0o644); err != nil {
		writeErr(w, 500, err.Error())
		return
	}
	row, err := s.Store.SetQuestlineIcon(r.Context(), id, name)
	if err != nil {
		writeErr(w, 500, err.Error())
		return
	}
	writeJSON(w, 200, row)
}

func (s *Server) deleteQuestlineIcon(w http.ResponseWriter, r *http.Request) {
	id, _ := strconv.ParseInt(r.PathValue("id"), 10, 64)
	row, err := s.Store.ClearQuestlineIcon(r.Context(), id, s.DataDir)
	if errors.Is(err, store.ErrNotFound) {
		writeErr(w, 404, "Questline not found")
		return
	}
	if err != nil {
		writeErr(w, 500, err.Error())
		return
	}
	writeJSON(w, 200, row)
}

func (s *Server) listTemplates(w http.ResponseWriter, r *http.Request) {
	var en *bool
	if v := r.URL.Query().Get("enabled"); v != "" {
		b := v == "1" || strings.EqualFold(v, "true")
		en = &b
	}
	rows, err := s.Store.ListTemplates(r.Context(), en)
	if err != nil {
		writeErr(w, 500, err.Error())
		return
	}
	writeJSON(w, 200, rows)
}

func (s *Server) getTemplate(w http.ResponseWriter, r *http.Request) {
	id, _ := strconv.ParseInt(r.PathValue("id"), 10, 64)
	row, err := s.Store.GetTemplate(r.Context(), id)
	if errors.Is(err, store.ErrNotFound) {
		writeErr(w, 404, "Template not found")
		return
	}
	if err != nil {
		writeErr(w, 500, err.Error())
		return
	}
	writeJSON(w, 200, row)
}

func (s *Server) createTemplate(w http.ResponseWriter, r *http.Request) {
	var body map[string]any
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
		writeErr(w, 400, "invalid JSON")
		return
	}
	row, err := s.Store.CreateTemplate(r.Context(), body)
	if err != nil {
		writeErr(w, 400, err.Error())
		return
	}
	if asBool(row["enabled"], true) {
		_, _ = schedule.MaterializeDue(r.Context(), s.Store, s.Hub, time.Time{}, nil)
	}
	writeJSON(w, 201, row)
}

func (s *Server) patchTemplate(w http.ResponseWriter, r *http.Request) {
	id, _ := strconv.ParseInt(r.PathValue("id"), 10, 64)
	var body map[string]any
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
		writeErr(w, 400, "invalid JSON")
		return
	}
	row, err := s.Store.UpdateTemplate(r.Context(), id, body)
	if errors.Is(err, store.ErrNotFound) {
		writeErr(w, 404, "Template not found")
		return
	}
	if err != nil {
		writeErr(w, 500, err.Error())
		return
	}
	if asBool(row["enabled"], false) {
		_, _ = schedule.MaterializeDue(r.Context(), s.Store, s.Hub, time.Time{}, nil)
	}
	writeJSON(w, 200, row)
}

func (s *Server) deleteTemplate(w http.ResponseWriter, r *http.Request) {
	id, _ := strconv.ParseInt(r.PathValue("id"), 10, 64)
	if err := s.Store.DeleteTemplate(r.Context(), id); err != nil {
		if errors.Is(err, store.ErrNotFound) {
			writeErr(w, 404, "Template not found")
			return
		}
		writeErr(w, 500, err.Error())
		return
	}
	w.WriteHeader(204)
}

func (s *Server) copyTemplate(w http.ResponseWriter, r *http.Request) {
	id, _ := strconv.ParseInt(r.PathValue("id"), 10, 64)
	row, err := s.Store.CopyTemplate(r.Context(), id)
	if errors.Is(err, store.ErrNotFound) {
		writeErr(w, 404, "Template not found")
		return
	}
	if err != nil {
		writeErr(w, 500, err.Error())
		return
	}
	writeJSON(w, 201, row)
}

func (s *Server) getHero(w http.ResponseWriter, r *http.Request) {
	row, err := s.Store.GetHero(r.Context())
	if err != nil {
		writeErr(w, 500, err.Error())
		return
	}
	writeJSON(w, 200, row)
}

func (s *Server) getStats(w http.ResponseWriter, r *http.Request) {
	days := 30
	if v := r.URL.Query().Get("days"); v != "" {
		if n, err := strconv.Atoi(v); err == nil {
			days = n
		}
	}
	var tid *int64
	if v := r.URL.Query().Get("template_id"); v != "" {
		if n, err := strconv.ParseInt(v, 10, 64); err == nil {
			tid = &n
		}
	}
	row, err := s.Store.BuildStats(r.Context(), days, tid)
	if errors.Is(err, store.ErrNotFound) {
		writeErr(w, 404, "Template not found")
		return
	}
	if err != nil {
		writeErr(w, 500, err.Error())
		return
	}
	writeJSON(w, 200, row)
}

func (s *Server) getQuestLog(w http.ResponseWriter, r *http.Request) {
	limit := 100
	if v := r.URL.Query().Get("limit"); v != "" {
		if n, err := strconv.Atoi(v); err == nil {
			limit = n
		}
	}
	var qid, before *int64
	if v := r.URL.Query().Get("quest_id"); v != "" {
		if n, err := strconv.ParseInt(v, 10, 64); err == nil {
			qid = &n
		}
	}
	if v := r.URL.Query().Get("before_id"); v != "" {
		if n, err := strconv.ParseInt(v, 10, 64); err == nil {
			before = &n
		}
	}
	rows, err := s.Store.ListChangeLog(r.Context(), limit, qid, before)
	if err != nil {
		writeErr(w, 500, err.Error())
		return
	}
	writeJSON(w, 200, rows)
}

func (s *Server) getContext(w http.ResponseWriter, r *http.Request) {
	q := r.URL.Query()
	var focusType string
	var focusID int64
	n := 0
	if v := q.Get("quest"); v != "" {
		id, err := strconv.ParseInt(v, 10, 64)
		if err == nil {
			focusType, focusID, n = "quest", id, n+1
		}
	}
	if v := q.Get("step"); v != "" {
		id, err := strconv.ParseInt(v, 10, 64)
		if err == nil {
			focusType, focusID, n = "step", id, n+1
		}
	}
	if v := q.Get("questline"); v != "" {
		id, err := strconv.ParseInt(v, 10, 64)
		if err == nil {
			focusType, focusID, n = "questline", id, n+1
		}
	}
	if n != 1 {
		writeErr(w, 400, "pass exactly one of quest, step, questline")
		return
	}
	var lineID *int64
	var quests []domain.Quest
	switch focusType {
	case "questline":
		lineID = &focusID
	case "quest":
		qq, err := s.Store.GetQuest(r.Context(), focusID)
		if errors.Is(err, store.ErrNotFound) {
			writeErr(w, 404, "Quest not found")
			return
		}
		if err != nil {
			writeErr(w, 500, err.Error())
			return
		}
		lineID = qq.QuestlineID
		if lineID == nil {
			quests = []domain.Quest{qq}
		}
	case "step":
		qid, err := s.Store.QuestIDForStep(r.Context(), focusID)
		if errors.Is(err, store.ErrNotFound) {
			writeErr(w, 404, "Step not found")
			return
		}
		if err != nil {
			writeErr(w, 500, err.Error())
			return
		}
		qq, err := s.Store.GetQuest(r.Context(), qid)
		if err != nil {
			writeErr(w, 500, err.Error())
			return
		}
		lineID = qq.QuestlineID
		if lineID == nil {
			quests = []domain.Quest{qq}
		}
	}
	var line any
	if lineID != nil {
		lr, err := s.Store.GetQuestline(r.Context(), *lineID)
		if err != nil {
			writeErr(w, 404, "Questline not found")
			return
		}
		line = lr
		qs, err := s.Store.ListQuests(r.Context(), store.ListFilter{
			QuestlineID: lineID,
			NewestFirst: true,
		})
		if err != nil {
			writeErr(w, 500, err.Error())
			return
		}
		quests = qs
	}
	reads := make([]domain.QuestRead, 0, len(quests))
	for _, qq := range quests {
		reads = append(reads, domain.ToQuestRead(qq, timeutil.NowUTC()))
	}
	writeJSON(w, 200, map[string]any{
		"focus":     map[string]any{"type": focusType, "id": focusID},
		"questline": line,
		"quests":    reads,
	})
}

func asBool(v any, def bool) bool {
	switch t := v.(type) {
	case bool:
		return t
	default:
		return def
	}
}