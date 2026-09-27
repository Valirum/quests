package store

import (
	"context"

	"github.com/valirum/quests/go/internal/timeutil"
)

// BackupRow is one row of backuplog — one attempted DB snapshot.
type BackupRow struct {
	ID             int64
	Filename       string
	SizeBytes      int64
	CreatedAt      string // RFC3339 UTC, as stored
	WebdavUploaded bool
	Error          string
}

// InsertBackupLog records an attempted snapshot (successful or not — Error
// non-empty marks a failed attempt, kept for visibility rather than dropped).
func (s *Store) InsertBackupLog(ctx context.Context, filename string, sizeBytes int64, uploaded bool, errMsg string) (int64, error) {
	res, err := s.DB.ExecContext(ctx, `
		INSERT INTO backuplog (filename, size_bytes, created_at, webdav_uploaded, error)
		VALUES (?, ?, ?, ?, ?)`,
		filename, sizeBytes, timeutil.ToDBUTC(timeutil.NowUTC()), boolInt(uploaded), nullStrVal(errMsg),
	)
	if err != nil {
		return 0, err
	}
	return res.LastInsertId()
}

// MarkBackupUploaded flips webdav_uploaded=1 once the WebDAV PUT succeeds
// (InsertBackupLog runs before the upload attempt, so the row exists first).
func (s *Store) MarkBackupUploaded(ctx context.Context, id int64) error {
	_, err := s.DB.ExecContext(ctx, `UPDATE backuplog SET webdav_uploaded=1 WHERE id=?`, id)
	return err
}

// ListBackupLogs returns every row, newest first — the rotation source of
// truth (not a WebDAV directory listing, which the client doesn't support).
func (s *Store) ListBackupLogs(ctx context.Context) ([]BackupRow, error) {
	rows, err := s.DB.QueryContext(ctx, `
		SELECT id, filename, size_bytes, created_at, webdav_uploaded, COALESCE(error, '')
		FROM backuplog ORDER BY created_at DESC, id DESC`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []BackupRow
	for rows.Next() {
		var r BackupRow
		var uploaded int
		if err := rows.Scan(&r.ID, &r.Filename, &r.SizeBytes, &r.CreatedAt, &uploaded, &r.Error); err != nil {
			return nil, err
		}
		r.WebdavUploaded = uploaded != 0
		out = append(out, r)
	}
	return out, rows.Err()
}

func (s *Store) DeleteBackupLog(ctx context.Context, id int64) error {
	_, err := s.DB.ExecContext(ctx, `DELETE FROM backuplog WHERE id=?`, id)
	return err
}

func nullStrVal(s string) any {
	if s == "" {
		return nil
	}
	return s
}
