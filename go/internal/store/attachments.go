package store

import (
	"context"
	"database/sql"
	"time"

	"github.com/valirum/quests/go/internal/timeutil"
)

// Attachment is metadata only — the bytes live on WebDAV at WebDAVPath.
type Attachment struct {
	ID                  int64
	OwnerType           string
	OwnerID             int64
	Filename            string
	WebDAVPath          string
	SizeBytes           int64
	ContentTypeDeclared string
	ContentTypeDetected string
	Comment             string
	UploadedAt          time.Time
	ScanStatus          string
	ScannedAt           *time.Time
}

type AttachmentRead map[string]any

const attachmentCols = `id, owner_type, owner_id, filename, webdav_path, size_bytes,
	content_type_declared, content_type_detected, comment, uploaded_at, scan_status, scanned_at`

func scanAttachment(row rowScanner) (Attachment, error) {
	var a Attachment
	var uploaded string
	var scanned sql.NullString
	err := row.Scan(&a.ID, &a.OwnerType, &a.OwnerID, &a.Filename, &a.WebDAVPath, &a.SizeBytes,
		&a.ContentTypeDeclared, &a.ContentTypeDetected, &a.Comment, &uploaded, &a.ScanStatus, &scanned)
	if err != nil {
		return a, err
	}
	if t, err := timeutil.ParseFlexible(uploaded); err == nil {
		a.UploadedAt = t
	}
	if scanned.Valid && scanned.String != "" {
		if t, err := timeutil.ParseFlexible(scanned.String); err == nil {
			a.ScannedAt = &t
		}
	}
	return a, nil
}

// AttachmentToRead shapes the JSON. WebDAVPath is deliberately absent: clients
// fetch through the API, and the storage layout is not their business.
func AttachmentToRead(a Attachment) AttachmentRead {
	return AttachmentRead{
		"id":                    a.ID,
		"owner_type":            a.OwnerType,
		"owner_id":              a.OwnerID,
		"filename":              a.Filename,
		"size_bytes":            a.SizeBytes,
		"content_type_declared": a.ContentTypeDeclared,
		"content_type_detected": a.ContentTypeDetected,
		"comment":               a.Comment,
		"uploaded_at":           timeutil.ToUTCISO(&a.UploadedAt),
		"scan_status":           a.ScanStatus,
		"scanned_at":            timeutil.ToUTCISO(a.ScannedAt),
	}
}

func (s *Store) ListAttachments(ctx context.Context, ownerType string, ownerID int64) ([]Attachment, error) {
	rows, err := s.DB.QueryContext(ctx, `
		SELECT `+attachmentCols+`
		FROM attachment WHERE owner_type = ? AND owner_id = ?
		ORDER BY uploaded_at, id`, ownerType, ownerID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := make([]Attachment, 0)
	for rows.Next() {
		a, err := scanAttachment(rows)
		if err != nil {
			return nil, err
		}
		out = append(out, a)
	}
	return out, rows.Err()
}

// ListAllAttachments is every metadata row. Cheap (SQLite only) — use it to
// seed a client index without stating WebDAV for every file.
func (s *Store) ListAllAttachments(ctx context.Context) ([]Attachment, error) {
	rows, err := s.DB.QueryContext(ctx, `
		SELECT `+attachmentCols+`
		FROM attachment
		ORDER BY owner_type, owner_id, uploaded_at, id`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := make([]Attachment, 0)
	for rows.Next() {
		a, err := scanAttachment(rows)
		if err != nil {
			return nil, err
		}
		out = append(out, a)
	}
	return out, rows.Err()
}

func (s *Store) GetAttachment(ctx context.Context, id int64) (Attachment, error) {
	row := s.DB.QueryRowContext(ctx, `SELECT `+attachmentCols+` FROM attachment WHERE id = ?`, id)
	a, err := scanAttachment(row)
	if err == sql.ErrNoRows {
		return Attachment{}, ErrNotFound
	}
	return a, err
}

func (s *Store) CreateAttachment(ctx context.Context, a Attachment) (Attachment, error) {
	now := timeutil.NowUTC()
	if a.UploadedAt.IsZero() {
		a.UploadedAt = now
	}
	var scanned any
	if a.ScannedAt != nil {
		scanned = timeutil.ToDBUTC(*a.ScannedAt)
	}
	res, err := s.DB.ExecContext(ctx, `
		INSERT INTO attachment (owner_type, owner_id, filename, webdav_path, size_bytes,
			content_type_declared, content_type_detected, comment, uploaded_at, scan_status, scanned_at)
		VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
		a.OwnerType, a.OwnerID, a.Filename, a.WebDAVPath, a.SizeBytes,
		a.ContentTypeDeclared, a.ContentTypeDetected, a.Comment,
		timeutil.ToDBUTC(a.UploadedAt), a.ScanStatus, scanned)
	if err != nil {
		return Attachment{}, err
	}
	id, err := res.LastInsertId()
	if err != nil {
		return Attachment{}, err
	}
	a.ID = id
	return a, nil
}

func (s *Store) SetAttachmentComment(ctx context.Context, id int64, comment string) (Attachment, error) {
	res, err := s.DB.ExecContext(ctx, `UPDATE attachment SET comment = ? WHERE id = ?`, comment, id)
	if err != nil {
		return Attachment{}, err
	}
	if n, _ := res.RowsAffected(); n == 0 {
		return Attachment{}, ErrNotFound
	}
	return s.GetAttachment(ctx, id)
}

func (s *Store) DeleteAttachment(ctx context.Context, id int64) error {
	res, err := s.DB.ExecContext(ctx, `DELETE FROM attachment WHERE id = ?`, id)
	if err != nil {
		return err
	}
	if n, _ := res.RowsAffected(); n == 0 {
		return ErrNotFound
	}
	return nil
}

// AttachmentPathsForOwner returns the WebDAV paths belonging to an owner, so a
// quest/questline delete can clean up the stored bytes too. There is no FK to
// cascade on — owner_id points at two different tables depending on owner_type.
func (s *Store) AttachmentPathsForOwner(ctx context.Context, ownerType string, ownerID int64) ([]string, error) {
	rows, err := s.DB.QueryContext(ctx,
		`SELECT webdav_path FROM attachment WHERE owner_type = ? AND owner_id = ?`, ownerType, ownerID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []string
	for rows.Next() {
		var p string
		if err := rows.Scan(&p); err != nil {
			return nil, err
		}
		out = append(out, p)
	}
	return out, rows.Err()
}

func (s *Store) DeleteAttachmentsForOwner(ctx context.Context, ownerType string, ownerID int64) error {
	_, err := s.DB.ExecContext(ctx,
		`DELETE FROM attachment WHERE owner_type = ? AND owner_id = ?`, ownerType, ownerID)
	return err
}
