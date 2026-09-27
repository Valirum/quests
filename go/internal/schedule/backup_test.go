package schedule

import (
	"context"
	"database/sql"
	"io"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"testing"

	_ "modernc.org/sqlite"

	"github.com/valirum/quests/go/internal/health"
	"github.com/valirum/quests/go/internal/store"
	"github.com/valirum/quests/go/internal/webdav"
)

// newFakeDAV is a minimal in-memory WebDAV stand-in — enough for Put/Delete,
// which is all the backup uploader needs.
func newFakeDAV(t *testing.T) *httptest.Server {
	t.Helper()
	var mu sync.Mutex
	files := map[string][]byte{}
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		path := strings.Trim(r.URL.Path, "/")
		switch r.Method {
		case "MKCOL":
			w.WriteHeader(http.StatusCreated)
		case http.MethodPut:
			body, _ := io.ReadAll(r.Body)
			mu.Lock()
			files[path] = body
			mu.Unlock()
			w.WriteHeader(http.StatusCreated)
		case http.MethodDelete:
			mu.Lock()
			_, ok := files[path]
			delete(files, path)
			mu.Unlock()
			if !ok {
				http.NotFound(w, r)
				return
			}
			w.WriteHeader(http.StatusNoContent)
		default:
			w.WriteHeader(http.StatusMethodNotAllowed)
		}
	}))
	t.Cleanup(srv.Close)
	return srv
}

const backupTestSchema = `
CREATE TABLE quest (
	id INTEGER PRIMARY KEY,
	title TEXT NOT NULL
);
CREATE TABLE backuplog (
	id INTEGER PRIMARY KEY,
	filename TEXT NOT NULL,
	size_bytes INTEGER NOT NULL,
	created_at DATETIME NOT NULL,
	webdav_uploaded INTEGER NOT NULL DEFAULT 0,
	error TEXT
);
`

func openBackupDB(t *testing.T) *store.Store {
	t.Helper()
	db, err := sql.Open("sqlite", "file:backup_"+t.Name()+"?mode=memory&cache=shared")
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { _ = db.Close() })
	db.SetMaxOpenConns(1)
	if _, err := db.Exec(backupTestSchema); err != nil {
		t.Fatal(err)
	}
	if _, err := db.Exec(`INSERT INTO quest (title) VALUES ('seed')`); err != nil {
		t.Fatal(err)
	}
	return &store.Store{DB: db}
}

func TestRunBackupOnceSnapshotsAndRecords(t *testing.T) {
	st := openBackupDB(t)
	dataDir := t.TempDir()
	reg := health.New()

	if err := RunBackupOnce(context.Background(), st, webdav.New("", "", ""), dataDir, 14, reg); err != nil {
		t.Fatalf("RunBackupOnce: %v", err)
	}

	entries, err := os.ReadDir(filepath.Join(dataDir, backupSubdir))
	if err != nil {
		t.Fatalf("read backups dir: %v", err)
	}
	if len(entries) != 1 {
		t.Fatalf("want 1 snapshot file, got %d", len(entries))
	}

	rows, err := st.ListBackupLogs(context.Background())
	if err != nil {
		t.Fatalf("ListBackupLogs: %v", err)
	}
	if len(rows) != 1 {
		t.Fatalf("want 1 backuplog row, got %d", len(rows))
	}
	if rows[0].WebdavUploaded {
		t.Fatal("unconfigured webdav should not mark uploaded")
	}
	if rows[0].SizeBytes <= 0 {
		t.Fatal("snapshot should have nonzero size")
	}
}

func TestRunBackupOncePrunesToKeep(t *testing.T) {
	st := openBackupDB(t)
	dataDir := t.TempDir()
	reg := health.New()
	wd := webdav.New("", "", "")

	for i := 0; i < 3; i++ {
		if err := RunBackupOnce(context.Background(), st, wd, dataDir, 2, reg); err != nil {
			t.Fatalf("RunBackupOnce #%d: %v", i, err)
		}
	}

	rows, err := st.ListBackupLogs(context.Background())
	if err != nil {
		t.Fatalf("ListBackupLogs: %v", err)
	}
	if len(rows) != 2 {
		t.Fatalf("want 2 rows after pruning to keep=2, got %d", len(rows))
	}

	entries, err := os.ReadDir(filepath.Join(dataDir, backupSubdir))
	if err != nil {
		t.Fatalf("read backups dir: %v", err)
	}
	if len(entries) != 2 {
		t.Fatalf("want 2 files on disk after pruning, got %d", len(entries))
	}
}

func TestRunBackupOnceUploadsAndPrunesWebdav(t *testing.T) {
	st := openBackupDB(t)
	dataDir := t.TempDir()
	reg := health.New()
	dav := newFakeDAV(t)
	wd := webdav.New(dav.URL, "", "")

	for i := 0; i < 3; i++ {
		if err := RunBackupOnce(context.Background(), st, wd, dataDir, 2, reg); err != nil {
			t.Fatalf("RunBackupOnce #%d: %v", i, err)
		}
	}

	rows, err := st.ListBackupLogs(context.Background())
	if err != nil {
		t.Fatalf("ListBackupLogs: %v", err)
	}
	if len(rows) != 2 {
		t.Fatalf("want 2 rows after pruning to keep=2, got %d", len(rows))
	}
	for _, r := range rows {
		if !r.WebdavUploaded {
			t.Fatalf("row %d (%s) should be marked webdav_uploaded", r.ID, r.Filename)
		}
	}
}
