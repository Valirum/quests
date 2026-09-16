package httpapi

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"path"
	"strconv"
	"strings"
	"time"

	"github.com/gabriel-vasile/mimetype"
	"github.com/google/uuid"

	"github.com/valirum/quests/go/internal/store"
	"github.com/valirum/quests/go/internal/timeutil"
	"github.com/valirum/quests/go/internal/webdav"
)

const (
	ownerQuest     = "quest"
	ownerQuestline = "questline"
)

func (s *Server) registerAttachments(mux *http.ServeMux) {
	for _, owner := range []struct{ seg, typ string }{
		{"quests", ownerQuest},
		{"questlines", ownerQuestline},
	} {
		seg, typ := owner.seg, owner.typ
		mux.HandleFunc("GET /api/"+seg+"/{id}/attachments", func(w http.ResponseWriter, r *http.Request) {
			s.listAttachments(w, r, typ)
		})
		mux.HandleFunc("POST /api/"+seg+"/{id}/attachments", func(w http.ResponseWriter, r *http.Request) {
			s.postAttachment(w, r, typ)
		})
		mux.HandleFunc("GET /api/"+seg+"/{id}/attachments/{aid}", func(w http.ResponseWriter, r *http.Request) {
			s.getAttachmentContent(w, r, typ)
		})
		mux.HandleFunc("PATCH /api/"+seg+"/{id}/attachments/{aid}", func(w http.ResponseWriter, r *http.Request) {
			s.patchAttachment(w, r, typ)
		})
		mux.HandleFunc("DELETE /api/"+seg+"/{id}/attachments/{aid}", func(w http.ResponseWriter, r *http.Request) {
			s.deleteAttachment(w, r, typ)
		})
	}
}

func (s *Server) ownerExists(ctx context.Context, ownerType string, id int64) (bool, error) {
	if ownerType == ownerQuestline {
		return s.Store.QuestlineExists(ctx, id)
	}
	_, err := s.Store.GetQuest(ctx, id)
	if errors.Is(err, store.ErrNotFound) {
		return false, nil
	}
	return err == nil, err
}

// attachmentFor resolves {id}/{aid} and refuses an attachment that belongs to a
// different owner, so a valid id under the wrong quest is a 404, not a leak.
func (s *Server) attachmentFor(r *http.Request, ownerType string) (store.Attachment, error) {
	ownerID, _ := strconv.ParseInt(r.PathValue("id"), 10, 64)
	aid, _ := strconv.ParseInt(r.PathValue("aid"), 10, 64)
	a, err := s.Store.GetAttachment(r.Context(), aid)
	if err != nil {
		return store.Attachment{}, err
	}
	if a.OwnerType != ownerType || a.OwnerID != ownerID {
		return store.Attachment{}, store.ErrNotFound
	}
	return a, nil
}

func (s *Server) webdavOK() bool { return s.WebDAV != nil && s.WebDAV.Configured() }
func (s *Server) clamavOK() bool { return s.ClamAV != nil && s.ClamAV.Configured() }

func (s *Server) listAttachments(w http.ResponseWriter, r *http.Request, ownerType string) {
	id, _ := strconv.ParseInt(r.PathValue("id"), 10, 64)
	rows, err := s.Store.ListAttachments(r.Context(), ownerType, id)
	if err != nil {
		writeErr(w, 500, err.Error())
		return
	}
	ownerUpdated := s.ownerUpdatedAt(r.Context(), ownerType, id)
	probe := r.URL.Query().Get("stat") != "0"
	out := make([]store.AttachmentRead, 0, len(rows))
	for _, a := range rows {
		out = append(out, s.decorateAttachment(r.Context(), a, ownerUpdated, probe))
	}
	writeJSON(w, 200, out)
}

func (s *Server) ownerUpdatedAt(ctx context.Context, ownerType string, id int64) *time.Time {
	if ownerType == ownerQuestline {
		row, err := s.Store.GetQuestline(ctx, id)
		if err != nil {
			return nil
		}
		raw, _ := row["updated_at"].(string)
		if raw == "" {
			return nil
		}
		t, err := timeutil.ParseFlexible(raw)
		if err != nil {
			return nil
		}
		return &t
	}
	q, err := s.Store.GetQuest(ctx, id)
	if err != nil {
		return nil
	}
	t := q.UpdatedAt
	return &t
}

// decorateAttachment adds live file-server facts. available is false (and the
// download link should hide) when WebDAV is down — not an error on the listing.
// source_updated is the "актуализируй" marker: the file's Last-Modified is
// newer than the quest/questline it is attached to.
func (s *Server) decorateAttachment(ctx context.Context, a store.Attachment, ownerUpdated *time.Time, probe bool) store.AttachmentRead {
	out := store.AttachmentToRead(a)
	out["available"] = false
	out["source_updated"] = false
	out["last_modified"] = nil
	if !probe || !s.webdavOK() {
		return out
	}
	info, err := s.WebDAV.Stat(ctx, a.WebDAVPath)
	if err != nil {
		return out
	}
	out["available"] = true
	if !info.LastModified.IsZero() {
		out["last_modified"] = timeutil.ToUTCISO(&info.LastModified)
		if ownerUpdated != nil && info.LastModified.After(ownerUpdated.UTC()) {
			out["source_updated"] = true
		}
	}
	return out
}

func (s *Server) attachmentsForOwner(ctx context.Context, ownerType string, ownerID int64, probe bool) []store.AttachmentRead {
	rows, err := s.Store.ListAttachments(ctx, ownerType, ownerID)
	if err != nil {
		return []store.AttachmentRead{}
	}
	ownerUpdated := s.ownerUpdatedAt(ctx, ownerType, ownerID)
	out := make([]store.AttachmentRead, 0, len(rows))
	for _, a := range rows {
		out = append(out, s.decorateAttachment(ctx, a, ownerUpdated, probe))
	}
	return out
}

// purgeOwnerAttachments drops metadata first, then the bytes. A leftover file
// on WebDAV is inert; a row pointing at nothing is a broken link.
func (s *Server) purgeOwnerAttachments(ctx context.Context, ownerType string, ownerID int64) {
	paths, err := s.Store.AttachmentPathsForOwner(ctx, ownerType, ownerID)
	if err != nil {
		fmt.Printf("attachments: list paths for %s-%d: %v\n", ownerType, ownerID, err)
		return
	}
	if err := s.Store.DeleteAttachmentsForOwner(ctx, ownerType, ownerID); err != nil {
		fmt.Printf("attachments: delete rows for %s-%d: %v\n", ownerType, ownerID, err)
		return
	}
	if !s.webdavOK() {
		return
	}
	for _, p := range paths {
		if err := s.WebDAV.Delete(ctx, p); err != nil && !errors.Is(err, webdav.ErrNotFound) {
			fmt.Printf("attachments: file left on webdav %s: %v\n", p, err)
		}
	}
}

// safeFilename keeps the original name for humans but strips anything that
// could escape the storage directory. The stored name is uuid-prefixed anyway;
// this is belt and braces.
func safeFilename(name string) string {
	name = path.Base(strings.ReplaceAll(strings.TrimSpace(name), "\\", "/"))
	name = strings.TrimLeft(name, ".")
	name = strings.Map(func(r rune) rune {
		switch r {
		case '/', '\x00', '\n', '\r':
			return -1
		}
		return r
	}, name)
	if name == "" {
		name = "file"
	}
	if len(name) > 200 {
		name = name[:200]
	}
	return name
}

func (s *Server) postAttachment(w http.ResponseWriter, r *http.Request, ownerType string) {
	if !s.webdavOK() {
		writeErr(w, 503, "attachment storage is not configured (QUESTS_WEBDAV_URL)")
		return
	}
	// No scanner means no upload. Storing something unscanned and calling it
	// "pending" would leave a file nobody ever goes back to check.
	if !s.clamavOK() {
		writeErr(w, 503, "virus scanning is not configured (QUESTS_CLAMAV_ADDR)")
		return
	}
	ownerID, _ := strconv.ParseInt(r.PathValue("id"), 10, 64)
	ok, err := s.ownerExists(r.Context(), ownerType, ownerID)
	if err != nil {
		writeErr(w, 500, err.Error())
		return
	}
	if !ok {
		writeErr(w, 404, "owner not found")
		return
	}

	maxBytes := s.MaxUploadBytes
	if maxBytes <= 0 {
		maxBytes = 25 << 20
	}
	r.Body = http.MaxBytesReader(w, r.Body, maxBytes+(1<<20))
	if err := r.ParseMultipartForm(8 << 20); err != nil {
		writeErr(w, 400, "invalid multipart (or file too large)")
		return
	}
	file, hdr, err := r.FormFile("file")
	if err != nil {
		writeErr(w, 400, "file required")
		return
	}
	defer file.Close()

	raw, err := io.ReadAll(io.LimitReader(file, maxBytes+1))
	if err != nil {
		writeErr(w, 400, "could not read upload")
		return
	}
	if len(raw) == 0 {
		writeErr(w, 400, "empty file")
		return
	}
	if int64(len(raw)) > maxBytes {
		writeErr(w, 413, fmt.Sprintf("file exceeds %d MB", maxBytes>>20))
		return
	}

	declared := strings.TrimSpace(hdr.Header.Get("Content-Type"))
	detected := mimetype.Detect(raw).String()

	res, err := s.ClamAV.Scan(r.Context(), bytes.NewReader(raw))
	if err != nil {
		// Unknown is not clean: refuse instead of storing an unscanned file.
		writeErr(w, 503, "virus scan unavailable: "+err.Error())
		return
	}
	if res.Infected {
		writeErr(w, 422, "file rejected by virus scan: "+res.Signature)
		return
	}

	filename := safeFilename(hdr.Filename)
	storedName := uuid.NewString() + "-" + filename
	webdavPath := fmt.Sprintf("attachments/%s-%d/%s", ownerType, ownerID, storedName)

	ctype := declared
	if ctype == "" {
		ctype = detected
	}
	if err := s.WebDAV.Put(r.Context(), webdavPath, ctype, bytes.NewReader(raw), int64(len(raw))); err != nil {
		writeErr(w, 502, "upload to file server failed: "+err.Error())
		return
	}

	now := timeutil.NowUTC()
	a, err := s.Store.CreateAttachment(r.Context(), store.Attachment{
		OwnerType:           ownerType,
		OwnerID:             ownerID,
		Filename:            filename,
		WebDAVPath:          webdavPath,
		SizeBytes:           int64(len(raw)),
		ContentTypeDeclared: declared,
		ContentTypeDetected: detected,
		Comment:             strings.TrimSpace(r.FormValue("comment")),
		UploadedAt:          now,
		ScanStatus:          "clean",
		ScannedAt:           &now,
	})
	if err != nil {
		// Don't leave bytes behind that no row points at.
		_ = s.WebDAV.Delete(context.WithoutCancel(r.Context()), webdavPath)
		writeErr(w, 500, err.Error())
		return
	}
	out := store.AttachmentToRead(a)
	out["available"] = true
	out["source_updated"] = false
	out["last_modified"] = nil
	writeJSON(w, 201, out)
}

func (s *Server) getAttachmentContent(w http.ResponseWriter, r *http.Request, ownerType string) {
	a, err := s.attachmentFor(r, ownerType)
	if errors.Is(err, store.ErrNotFound) {
		writeErr(w, 404, "attachment not found")
		return
	}
	if err != nil {
		writeErr(w, 500, err.Error())
		return
	}
	if !s.webdavOK() {
		writeErr(w, 503, "attachment storage is not configured")
		return
	}
	body, err := s.WebDAV.Get(r.Context(), a.WebDAVPath)
	if errors.Is(err, webdav.ErrNotFound) {
		writeErr(w, 404, "file missing on the file server")
		return
	}
	if err != nil {
		writeErr(w, 502, "file server unreachable: "+err.Error())
		return
	}
	defer body.Close()

	// Always a download, never something the browser renders or sniffs into
	// executing. This — not an extension blocklist — is what keeps a hostile
	// file harmless on the way out.
	w.Header().Set("Content-Type", "application/octet-stream")
	w.Header().Set("X-Content-Type-Options", "nosniff")
	w.Header().Set("Content-Disposition", contentDisposition(a.Filename))
	if a.SizeBytes > 0 {
		w.Header().Set("Content-Length", strconv.FormatInt(a.SizeBytes, 10))
	}
	w.WriteHeader(200)
	_, _ = io.Copy(w, body)
}

// contentDisposition sends an ASCII fallback plus RFC 5987 UTF-8, so a Russian
// filename survives without breaking older clients.
func contentDisposition(name string) string {
	ascii := strings.Map(func(r rune) rune {
		if r < 32 || r > 126 || r == '"' || r == '\\' {
			return '_'
		}
		return r
	}, name)
	return fmt.Sprintf(`attachment; filename="%s"; filename*=UTF-8''%s`,
		ascii, urlEscapePath(name))
}

func urlEscapePath(s string) string {
	var b strings.Builder
	for _, c := range []byte(s) {
		if (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') || (c >= '0' && c <= '9') ||
			c == '-' || c == '_' || c == '.' || c == '~' {
			b.WriteByte(c)
			continue
		}
		fmt.Fprintf(&b, "%%%02X", c)
	}
	return b.String()
}

func (s *Server) patchAttachment(w http.ResponseWriter, r *http.Request, ownerType string) {
	a, err := s.attachmentFor(r, ownerType)
	if errors.Is(err, store.ErrNotFound) {
		writeErr(w, 404, "attachment not found")
		return
	}
	if err != nil {
		writeErr(w, 500, err.Error())
		return
	}
	var body struct {
		Comment *string `json:"comment"`
	}
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
		writeErr(w, 400, "invalid JSON")
		return
	}
	if body.Comment == nil {
		writeJSON(w, 200, store.AttachmentToRead(a))
		return
	}
	updated, err := s.Store.SetAttachmentComment(r.Context(), a.ID, strings.TrimSpace(*body.Comment))
	if err != nil {
		writeErr(w, 500, err.Error())
		return
	}
	writeJSON(w, 200, store.AttachmentToRead(updated))
}

func (s *Server) deleteAttachment(w http.ResponseWriter, r *http.Request, ownerType string) {
	a, err := s.attachmentFor(r, ownerType)
	if errors.Is(err, store.ErrNotFound) {
		writeErr(w, 404, "attachment not found")
		return
	}
	if err != nil {
		writeErr(w, 500, err.Error())
		return
	}
	// Drop the row first: a leftover file on WebDAV is inert, a row pointing at
	// nothing is a broken link in the UI.
	if err := s.Store.DeleteAttachment(r.Context(), a.ID); err != nil {
		writeErr(w, 500, err.Error())
		return
	}
	if s.webdavOK() {
		if err := s.WebDAV.Delete(r.Context(), a.WebDAVPath); err != nil && !errors.Is(err, webdav.ErrNotFound) {
			// The row is already gone; report success but don't hide the miss.
			fmt.Printf("attachment %d: file left on webdav: %v\n", a.ID, err)
		}
	}
	w.WriteHeader(204)
}
