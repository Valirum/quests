package schedule

import (
	"context"
	"fmt"
	"log"
	"os"
	"path/filepath"
	"time"

	"github.com/valirum/quests/go/internal/health"
	"github.com/valirum/quests/go/internal/store"
	"github.com/valirum/quests/go/internal/webdav"
)

// backupSubdir is where local snapshots live, under the data dir — sibling
// to the DB itself, not the OS temp dir, so it survives on the same volume
// that gets backed up/restored as a unit.
const backupSubdir = "backups"

// webdavBackupDir is the directory on the WebDAV server backups upload to,
// separate from the "attachments" tree that already lives there.
const webdavBackupDir = "backups"

// RunBackupLoop periodically snapshots the DB (VACUUM INTO — WAL-safe, no
// external sqlite3 binary needed), uploads it to WebDAV when configured, and
// prunes old snapshots. interval<=0 disables it entirely.
func RunBackupLoop(ctx context.Context, st *store.Store, wd *webdav.Client, dataDir string, interval time.Duration, keep int, reg *health.Registry) {
	if interval <= 0 {
		log.Printf("backup: disabled (QUESTS_BACKUP_INTERVAL_HOURS=0)")
		return
	}
	ticker := time.NewTicker(interval)
	defer ticker.Stop()
	for {
		if err := RunBackupOnce(ctx, st, wd, dataDir, keep, reg); err != nil {
			log.Printf("backup: %v", err)
		}
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
		}
	}
}

// RunBackupOnce takes one snapshot, uploads it, and prunes down to `keep`.
// Failures at each stage are recorded (backuplog row / health probe) rather
// than aborting the whole thing — a failed upload still keeps the local copy.
func RunBackupOnce(ctx context.Context, st *store.Store, wd *webdav.Client, dataDir string, keep int, reg *health.Registry) error {
	dir := filepath.Join(dataDir, backupSubdir)
	if err := os.MkdirAll(dir, 0o755); err != nil {
		reg.SetProbe("backup", "offline", err.Error())
		return fmt.Errorf("mkdir: %w", err)
	}

	now := time.Now().UTC()
	filename := fmt.Sprintf("quests-%s-%09d.db", now.Format("20060102-150405"), now.Nanosecond())
	localPath := filepath.Join(dir, filename)

	if _, err := st.DB.ExecContext(ctx, `VACUUM INTO ?`, localPath); err != nil {
		reg.SetProbe("backup", "offline", err.Error())
		_, _ = st.InsertBackupLog(ctx, filename, 0, false, err.Error())
		return fmt.Errorf("vacuum into: %w", err)
	}

	info, err := os.Stat(localPath)
	if err != nil {
		reg.SetProbe("backup", "offline", err.Error())
		_, _ = st.InsertBackupLog(ctx, filename, 0, false, err.Error())
		return fmt.Errorf("stat snapshot: %w", err)
	}

	id, err := st.InsertBackupLog(ctx, filename, info.Size(), false, "")
	if err != nil {
		return fmt.Errorf("record backuplog: %w", err)
	}

	uploaded := false
	if wd.Configured() {
		f, err := os.Open(localPath)
		if err != nil {
			log.Printf("backup: reopen %s for upload: %v", filename, err)
		} else {
			putErr := wd.Put(ctx, webdavBackupDir+"/"+filename, "application/x-sqlite3", f, info.Size())
			f.Close()
			if putErr != nil {
				log.Printf("backup: webdav upload %s: %v", filename, putErr)
			} else if err := st.MarkBackupUploaded(ctx, id); err != nil {
				log.Printf("backup: mark uploaded %s: %v", filename, err)
			} else {
				uploaded = true
			}
		}
	}

	detail := fmt.Sprintf("%s (%d bytes, webdav=%v)", filename, info.Size(), uploaded)
	reg.SetProbe("backup", "ok", detail)

	if err := pruneBackups(ctx, st, wd, dir, keep); err != nil {
		log.Printf("backup: prune: %v", err)
	}
	return nil
}

// pruneBackups keeps the `keep` most recent rows (by backuplog, the source
// of truth — not a WebDAV listing, which the client doesn't support) and
// removes the rest: local file, WebDAV object (if uploaded), and the row.
func pruneBackups(ctx context.Context, st *store.Store, wd *webdav.Client, dir string, keep int) error {
	if keep <= 0 {
		return nil
	}
	rows, err := st.ListBackupLogs(ctx)
	if err != nil {
		return err
	}
	if len(rows) <= keep {
		return nil
	}
	for _, r := range rows[keep:] {
		if err := os.Remove(filepath.Join(dir, r.Filename)); err != nil && !os.IsNotExist(err) {
			log.Printf("backup: prune local %s: %v", r.Filename, err)
		}
		if r.WebdavUploaded && wd.Configured() {
			if err := wd.Delete(ctx, webdavBackupDir+"/"+r.Filename); err != nil && err != webdav.ErrNotFound {
				log.Printf("backup: prune webdav %s: %v", r.Filename, err)
			}
		}
		if err := st.DeleteBackupLog(ctx, r.ID); err != nil {
			log.Printf("backup: prune backuplog row %d: %v", r.ID, err)
		}
	}
	return nil
}
