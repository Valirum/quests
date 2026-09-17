package httpapi

import (
	"bytes"
	"database/sql"
	"encoding/binary"
	"encoding/json"
	"fmt"
	"io"
	"mime/multipart"
	"net"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync"
	"testing"
	"time"

	_ "modernc.org/sqlite"

	"github.com/valirum/quests/go/internal/clamav"
	"github.com/valirum/quests/go/internal/domain"
	"github.com/valirum/quests/go/internal/events"
	"github.com/valirum/quests/go/internal/store"
	"github.com/valirum/quests/go/internal/timeutil"
	"github.com/valirum/quests/go/internal/webdav"
)

const attachmentsSchema = `
CREATE TABLE questcategory (
	id INTEGER PRIMARY KEY,
	slug TEXT NOT NULL,
	label TEXT NOT NULL,
	sort_order INTEGER NOT NULL DEFAULT 0,
	color TEXT NOT NULL DEFAULT '#9a9a9a',
	created_at DATETIME NOT NULL
);
CREATE TABLE questline (
	id INTEGER PRIMARY KEY,
	title TEXT NOT NULL,
	description TEXT NOT NULL DEFAULT '',
	category_id INTEGER,
	color TEXT NOT NULL DEFAULT '#9a9a9a',
	icon TEXT NOT NULL DEFAULT 'document',
	custom_icon TEXT,
	created_at DATETIME NOT NULL,
	updated_at DATETIME NOT NULL
);
CREATE TABLE quest (
	id INTEGER PRIMARY KEY,
	title TEXT NOT NULL,
	description TEXT NOT NULL DEFAULT '',
	status TEXT NOT NULL,
	significance TEXT NOT NULL,
	pinned INTEGER NOT NULL DEFAULT 0,
	sort_order INTEGER NOT NULL DEFAULT 0,
	deadline_at DATETIME,
	duration_seconds INTEGER,
	reward_attrs TEXT,
	category_id INTEGER,
	questline_id INTEGER,
	created_at DATETIME NOT NULL,
	updated_at DATETIME NOT NULL,
	completed_at DATETIME,
	template_id INTEGER,
	period_key TEXT,
	automated INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE queststep (
	id INTEGER PRIMARY KEY,
	quest_id INTEGER NOT NULL,
	title TEXT NOT NULL,
	description TEXT NOT NULL DEFAULT '',
	progress_current INTEGER NOT NULL DEFAULT 0,
	progress_total INTEGER NOT NULL DEFAULT 1,
	sort_order INTEGER NOT NULL DEFAULT 0,
	check_command TEXT,
	check_interval_seconds INTEGER,
	check_last_run_at DATETIME,
	wait_previous INTEGER NOT NULL DEFAULT 0,
	run_mode TEXT NOT NULL DEFAULT 'poll',
	run_status TEXT
);
CREATE TABLE questchangelog (
	id INTEGER PRIMARY KEY,
	at DATETIME NOT NULL,
	kind TEXT NOT NULL,
	quest_id INTEGER,
	title TEXT NOT NULL DEFAULT '',
	detail TEXT NOT NULL DEFAULT '',
	significance TEXT,
	revision INTEGER,
	comment TEXT
);
CREATE TABLE questtemplate (
	id INTEGER PRIMARY KEY,
	questline_id INTEGER
);
CREATE TABLE metricledger (
	id INTEGER PRIMARY KEY,
	quest_id INTEGER
);
CREATE TABLE attachment (
	id INTEGER PRIMARY KEY,
	owner_type TEXT NOT NULL,
	owner_id INTEGER NOT NULL,
	filename TEXT NOT NULL,
	webdav_path TEXT NOT NULL UNIQUE,
	size_bytes INTEGER NOT NULL DEFAULT 0,
	content_type_declared TEXT NOT NULL DEFAULT '',
	content_type_detected TEXT NOT NULL DEFAULT '',
	comment TEXT NOT NULL DEFAULT '',
	uploaded_at DATETIME NOT NULL,
	scan_status TEXT NOT NULL DEFAULT 'pending',
	scanned_at DATETIME
);
CREATE TABLE note (
	id INTEGER PRIMARY KEY,
	title TEXT NOT NULL,
	description TEXT NOT NULL DEFAULT '',
	pinned INTEGER NOT NULL DEFAULT 0,
	sort_order INTEGER NOT NULL DEFAULT 0,
	parent_id INTEGER,
	color TEXT NOT NULL DEFAULT '#9a9a9a',
	icon TEXT NOT NULL DEFAULT 'document',
	custom_icon TEXT,
	created_at DATETIME NOT NULL,
	updated_at DATETIME NOT NULL
);
`

type davFile struct {
	body  []byte
	mod   time.Time
	ctype string
}

type fakeDAV struct {
	mu    sync.Mutex
	files map[string]davFile
}

func newFakeDAV() *httptest.Server {
	fs := &fakeDAV{files: map[string]davFile{}}
	return httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		path := strings.Trim(r.URL.Path, "/")
		switch r.Method {
		case "MKCOL":
			w.WriteHeader(http.StatusCreated)
		case http.MethodPut:
			body, _ := io.ReadAll(r.Body)
			fs.mu.Lock()
			fs.files[path] = davFile{
				body:  body,
				mod:   time.Now().UTC(),
				ctype: r.Header.Get("Content-Type"),
			}
			fs.mu.Unlock()
			w.WriteHeader(http.StatusCreated)
		case http.MethodGet:
			fs.mu.Lock()
			f, ok := fs.files[path]
			fs.mu.Unlock()
			if !ok {
				http.NotFound(w, r)
				return
			}
			w.Header().Set("Content-Type", "application/octet-stream")
			w.Header().Set("Last-Modified", f.mod.Format(http.TimeFormat))
			_, _ = w.Write(f.body)
		case http.MethodHead:
			fs.mu.Lock()
			f, ok := fs.files[path]
			fs.mu.Unlock()
			if !ok {
				http.NotFound(w, r)
				return
			}
			w.Header().Set("Last-Modified", f.mod.Format(http.TimeFormat))
			w.Header().Set("Content-Length", fmt.Sprintf("%d", len(f.body)))
			w.WriteHeader(http.StatusOK)
		case http.MethodDelete:
			fs.mu.Lock()
			_, ok := fs.files[path]
			delete(fs.files, path)
			fs.mu.Unlock()
			if !ok {
				http.NotFound(w, r)
				return
			}
			w.WriteHeader(http.StatusNoContent)
		default:
			w.WriteHeader(http.StatusMethodNotAllowed)
		}
	}))
}

// fakeClamd is the server half of INSTREAM, copied in spirit from clamav_test
// so httpapi tests don't import an internal test helper.
func fakeClamd(t *testing.T, reply string) string {
	t.Helper()
	ln, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatalf("listen: %v", err)
	}
	t.Cleanup(func() { _ = ln.Close() })
	go func() {
		for {
			conn, err := ln.Accept()
			if err != nil {
				return
			}
			go func(c net.Conn) {
				defer c.Close()
				buf := make([]byte, 1)
				for {
					n, err := c.Read(buf)
					if n > 0 && buf[0] == 0 {
						break
					}
					if err != nil {
						return
					}
				}
				var hdr [4]byte
				for {
					if _, err := io.ReadFull(c, hdr[:]); err != nil {
						return
					}
					size := binary.BigEndian.Uint32(hdr[:])
					if size == 0 {
						break
					}
					if _, err := io.CopyN(io.Discard, c, int64(size)); err != nil {
						return
					}
				}
				_, _ = c.Write([]byte(reply + "\x00"))
			}(conn)
		}
	}()
	return ln.Addr().String()
}

func newAttachmentServer(t *testing.T, davURL, clamAddr string, maxUpload int64) *Server {
	t.Helper()
	dsn := fmt.Sprintf("file:%s?mode=memory&cache=shared", t.Name())
	db, err := sql.Open("sqlite", dsn)
	if err != nil {
		t.Fatalf("open sqlite: %v", err)
	}
	db.SetMaxOpenConns(1)
	t.Cleanup(func() { _ = db.Close() })
	if _, err := db.Exec(attachmentsSchema); err != nil {
		t.Fatalf("schema: %v", err)
	}
	st := &store.Store{DB: db}
	if maxUpload <= 0 {
		maxUpload = 25 << 20
	}
	s := &Server{
		Store:          st,
		Hub:            events.New(),
		AuthRequired:   false,
		WebDAV:         webdav.New(davURL, "", ""),
		ClamAV:         clamav.New(clamAddr),
		MaxUploadBytes: maxUpload,
	}
	return s
}

func seedQuest(t *testing.T, s *Server) int64 {
	t.Helper()
	now := timeutil.NowUTC()
	q, err := s.Store.CreateQuest(t.Context(), domain.Quest{
		Title:        "with files",
		Status:       domain.StatusActive,
		Significance: domain.SigCommon,
		CreatedAt:    now,
		UpdatedAt:    now,
		Steps:        []domain.Step{{Title: "one", ProgressTotal: 1}},
	})
	if err != nil {
		t.Fatalf("create quest: %v", err)
	}
	return q.ID
}

func postFile(t *testing.T, h http.Handler, path, filename, comment string, body []byte) *httptest.ResponseRecorder {
	t.Helper()
	var buf bytes.Buffer
	mw := multipart.NewWriter(&buf)
	fw, err := mw.CreateFormFile("file", filename)
	if err != nil {
		t.Fatal(err)
	}
	if _, err := fw.Write(body); err != nil {
		t.Fatal(err)
	}
	if comment != "" {
		_ = mw.WriteField("comment", comment)
	}
	if err := mw.Close(); err != nil {
		t.Fatal(err)
	}
	r := httptest.NewRequest(http.MethodPost, path, &buf)
	r.Header.Set("Content-Type", mw.FormDataContentType())
	w := httptest.NewRecorder()
	h.ServeHTTP(w, r)
	return w
}

func TestAttachmentHappyPath(t *testing.T) {
	dav := newFakeDAV()
	t.Cleanup(dav.Close)
	clam := fakeClamd(t, "stream: OK")
	s := newAttachmentServer(t, dav.URL, clam, 0)
	qid := seedQuest(t, s)
	h := s.Handler()

	w := postFile(t, h, fmt.Sprintf("/api/quests/%d/attachments", qid), "note.txt", "todo source", []byte("hello files"))
	if w.Code != http.StatusCreated {
		t.Fatalf("upload status = %d body %s", w.Code, w.Body.String())
	}
	var created map[string]any
	if err := json.Unmarshal(w.Body.Bytes(), &created); err != nil {
		t.Fatal(err)
	}
	if created["filename"] != "note.txt" {
		t.Fatalf("filename = %v", created["filename"])
	}
	if created["comment"] != "todo source" {
		t.Fatalf("comment = %v", created["comment"])
	}
	if created["scan_status"] != "clean" {
		t.Fatalf("scan_status = %v", created["scan_status"])
	}
	if created["available"] != true {
		t.Fatalf("available = %v, want true after upload", created["available"])
	}
	aid := int64(created["id"].(float64))

	list := httptest.NewRecorder()
	h.ServeHTTP(list, httptest.NewRequest(http.MethodGet, fmt.Sprintf("/api/quests/%d/attachments", qid), nil))
	if list.Code != 200 {
		t.Fatalf("list = %d %s", list.Code, list.Body.String())
	}
	var rows []map[string]any
	if err := json.Unmarshal(list.Body.Bytes(), &rows); err != nil {
		t.Fatal(err)
	}
	if len(rows) != 1 {
		t.Fatalf("list len = %d", len(rows))
	}
	if rows[0]["available"] != true {
		t.Fatalf("listed available = %v", rows[0]["available"])
	}

	dl := httptest.NewRecorder()
	h.ServeHTTP(dl, httptest.NewRequest(http.MethodGet, fmt.Sprintf("/api/quests/%d/attachments/%d", qid, aid), nil))
	if dl.Code != 200 {
		t.Fatalf("download = %d %s", dl.Code, dl.Body.String())
	}
	if got := dl.Header().Get("Content-Disposition"); !strings.Contains(got, "attachment") {
		t.Fatalf("Content-Disposition = %q", got)
	}
	if dl.Header().Get("X-Content-Type-Options") != "nosniff" {
		t.Fatalf("missing nosniff")
	}
	if dl.Header().Get("Content-Type") != "application/octet-stream" {
		t.Fatalf("Content-Type = %q", dl.Header().Get("Content-Type"))
	}
	if dl.Body.String() != "hello files" {
		t.Fatalf("body = %q", dl.Body.String())
	}

	patch := doJSON(t, h, http.MethodPatch, fmt.Sprintf("/api/quests/%d/attachments/%d", qid, aid),
		map[string]string{"comment": "updated note"}, nil)
	if patch.Code != 200 {
		t.Fatalf("patch = %d %s", patch.Code, patch.Body.String())
	}

	del := httptest.NewRecorder()
	h.ServeHTTP(del, httptest.NewRequest(http.MethodDelete, fmt.Sprintf("/api/quests/%d/attachments/%d", qid, aid), nil))
	if del.Code != 204 {
		t.Fatalf("delete = %d %s", del.Code, del.Body.String())
	}
}

func TestAttachmentInfectedRejected(t *testing.T) {
	dav := newFakeDAV()
	t.Cleanup(dav.Close)
	clam := fakeClamd(t, "stream: Eicar-Test-Signature FOUND")
	s := newAttachmentServer(t, dav.URL, clam, 0)
	qid := seedQuest(t, s)
	w := postFile(t, s.Handler(), fmt.Sprintf("/api/quests/%d/attachments", qid), "eicar.txt", "", []byte("X5O!"))
	if w.Code != 422 {
		t.Fatalf("status = %d want 422 body %s", w.Code, w.Body.String())
	}
	if !strings.Contains(w.Body.String(), "Eicar-Test-Signature") {
		t.Fatalf("body = %s", w.Body.String())
	}
}

func TestAttachmentScannerDownIs503(t *testing.T) {
	dav := newFakeDAV()
	t.Cleanup(dav.Close)
	clam := fakeClamd(t, "INSTREAM size limit exceeded. ERROR")
	s := newAttachmentServer(t, dav.URL, clam, 0)
	qid := seedQuest(t, s)
	w := postFile(t, s.Handler(), fmt.Sprintf("/api/quests/%d/attachments", qid), "a.txt", "", []byte("ok"))
	if w.Code != 503 {
		t.Fatalf("status = %d want 503 body %s", w.Code, w.Body.String())
	}
}

func TestAttachmentTooLargeIs413(t *testing.T) {
	dav := newFakeDAV()
	t.Cleanup(dav.Close)
	clam := fakeClamd(t, "stream: OK")
	s := newAttachmentServer(t, dav.URL, clam, 8)
	qid := seedQuest(t, s)
	w := postFile(t, s.Handler(), fmt.Sprintf("/api/quests/%d/attachments", qid), "big.bin", "", bytes.Repeat([]byte("x"), 32))
	if w.Code != 413 {
		t.Fatalf("status = %d want 413 body %s", w.Code, w.Body.String())
	}
}

func TestAttachmentWrongOwnerIs404(t *testing.T) {
	dav := newFakeDAV()
	t.Cleanup(dav.Close)
	clam := fakeClamd(t, "stream: OK")
	s := newAttachmentServer(t, dav.URL, clam, 0)
	h := s.Handler()
	a := seedQuest(t, s)
	b := seedQuest(t, s)
	up := postFile(t, h, fmt.Sprintf("/api/quests/%d/attachments", a), "x.txt", "", []byte("x"))
	if up.Code != 201 {
		t.Fatalf("upload = %d %s", up.Code, up.Body.String())
	}
	var created map[string]any
	_ = json.Unmarshal(up.Body.Bytes(), &created)
	aid := int64(created["id"].(float64))

	w := httptest.NewRecorder()
	h.ServeHTTP(w, httptest.NewRequest(http.MethodGet, fmt.Sprintf("/api/quests/%d/attachments/%d", b, aid), nil))
	if w.Code != 404 {
		t.Fatalf("status = %d want 404 body %s", w.Code, w.Body.String())
	}
}

func TestAttachmentDeleteQuestPurgesFiles(t *testing.T) {
	davSrv := newFakeDAV()
	t.Cleanup(davSrv.Close)
	clam := fakeClamd(t, "stream: OK")
	s := newAttachmentServer(t, davSrv.URL, clam, 0)
	h := s.Handler()
	qid := seedQuest(t, s)
	up := postFile(t, h, fmt.Sprintf("/api/quests/%d/attachments", qid), "keep.txt", "", []byte("bye"))
	if up.Code != 201 {
		t.Fatalf("upload = %d %s", up.Code, up.Body.String())
	}

	del := httptest.NewRecorder()
	h.ServeHTTP(del, httptest.NewRequest(http.MethodDelete, fmt.Sprintf("/api/quests/%d", qid), nil))
	if del.Code != 204 {
		t.Fatalf("delete quest = %d %s", del.Code, del.Body.String())
	}
	rows, err := s.Store.ListAttachments(t.Context(), ownerQuest, qid)
	if err != nil {
		t.Fatal(err)
	}
	if len(rows) != 0 {
		t.Fatalf("rows left = %d", len(rows))
	}
}

func TestAttachmentUnconfiguredIs503(t *testing.T) {
	s := newAttachmentServer(t, "", "", 0)
	qid := seedQuest(t, s)
	w := postFile(t, s.Handler(), fmt.Sprintf("/api/quests/%d/attachments", qid), "a.txt", "", []byte("x"))
	if w.Code != 503 {
		t.Fatalf("status = %d want 503 body %s", w.Code, w.Body.String())
	}
}

func TestAttachmentSourceUpdatedMarker(t *testing.T) {
	dav := newFakeDAV()
	t.Cleanup(dav.Close)
	clam := fakeClamd(t, "stream: OK")
	s := newAttachmentServer(t, dav.URL, clam, 0)
	qid := seedQuest(t, s)
	h := s.Handler()
	up := postFile(t, h, fmt.Sprintf("/api/quests/%d/attachments", qid), "src.md", "", []byte("# todo"))
	if up.Code != 201 {
		t.Fatalf("upload = %d %s", up.Code, up.Body.String())
	}
	// File Last-Modified is "now"; backdate the quest so the marker fires.
	_, err := s.Store.DB.Exec(`UPDATE quest SET updated_at = ? WHERE id = ?`,
		timeutil.ToDBUTC(time.Now().UTC().Add(-2*time.Hour)), qid)
	if err != nil {
		t.Fatal(err)
	}
	list := httptest.NewRecorder()
	h.ServeHTTP(list, httptest.NewRequest(http.MethodGet, fmt.Sprintf("/api/quests/%d/attachments", qid), nil))
	var rows []map[string]any
	if err := json.Unmarshal(list.Body.Bytes(), &rows); err != nil {
		t.Fatal(err)
	}
	if len(rows) != 1 || rows[0]["source_updated"] != true {
		t.Fatalf("source_updated = %v rows=%v", rows, rows)
	}
}

func TestAttachmentIndexIsMetadataOnly(t *testing.T) {
	dav := newFakeDAV()
	t.Cleanup(dav.Close)
	clam := fakeClamd(t, "stream: OK")
	s := newAttachmentServer(t, dav.URL, clam, 0)
	a := seedQuest(t, s)
	b := seedQuest(t, s)
	h := s.Handler()

	if w := postFile(t, h, fmt.Sprintf("/api/quests/%d/attachments", a), "a.txt", "", []byte("aaa")); w.Code != 201 {
		t.Fatalf("upload a = %d %s", w.Code, w.Body.String())
	}
	if w := postFile(t, h, fmt.Sprintf("/api/quests/%d/attachments", b), "b.txt", "note", []byte("bbb")); w.Code != 201 {
		t.Fatalf("upload b = %d %s", w.Code, w.Body.String())
	}

	idx := httptest.NewRecorder()
	h.ServeHTTP(idx, httptest.NewRequest(http.MethodGet, "/api/attachments", nil))
	if idx.Code != 200 {
		t.Fatalf("index = %d %s", idx.Code, idx.Body.String())
	}
	var grouped map[string]map[string][]map[string]any
	if err := json.Unmarshal(idx.Body.Bytes(), &grouped); err != nil {
		t.Fatal(err)
	}
	if grouped["questline"] == nil || grouped["quest"] == nil {
		t.Fatalf("missing buckets: %v", grouped)
	}
	akey := fmt.Sprintf("%d", a)
	bkey := fmt.Sprintf("%d", b)
	if len(grouped["quest"][akey]) != 1 || grouped["quest"][akey][0]["filename"] != "a.txt" {
		t.Fatalf("quest a = %v", grouped["quest"][akey])
	}
	if grouped["quest"][bkey][0]["comment"] != "note" {
		t.Fatalf("quest b = %v", grouped["quest"][bkey])
	}
	if _, ok := grouped["quest"][akey][0]["available"]; ok {
		t.Fatalf("index must not Stat: available=%v", grouped["quest"][akey][0]["available"])
	}

	quiet := httptest.NewRecorder()
	h.ServeHTTP(quiet, httptest.NewRequest(http.MethodGet, fmt.Sprintf("/api/quests/%d/attachments?stat=0", a), nil))
	var quietRows []map[string]any
	if err := json.Unmarshal(quiet.Body.Bytes(), &quietRows); err != nil {
		t.Fatal(err)
	}
	if len(quietRows) != 1 {
		t.Fatalf("stat=0 len = %d", len(quietRows))
	}
	if _, ok := quietRows[0]["available"]; ok {
		t.Fatalf("stat=0 must omit available: %v", quietRows[0])
	}

	live := httptest.NewRecorder()
	h.ServeHTTP(live, httptest.NewRequest(http.MethodGet, "/api/attachments?stat=1", nil))
	if err := json.Unmarshal(live.Body.Bytes(), &grouped); err != nil {
		t.Fatal(err)
	}
	if grouped["quest"][akey][0]["available"] != true {
		t.Fatalf("stat=1 available = %v", grouped["quest"][akey][0]["available"])
	}
}
