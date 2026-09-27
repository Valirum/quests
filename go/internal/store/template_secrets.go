package store

import (
	"context"

	"github.com/valirum/quests/go/internal/timeutil"
)

// SetTemplateSecret upserts one secret value for a template. Stored as
// plaintext — the server itself is the trust boundary (emit_pool_command
// scripts run on the same host, same as the root .env already is) — but
// never returned by a read endpoint or MCP tool; see ResolveTemplateSecrets,
// the only reader, called from the exec path.
func (s *Store) SetTemplateSecret(ctx context.Context, templateID int64, name, value string) error {
	now := timeutil.ToDBUTC(timeutil.NowUTC())
	_, err := s.DB.ExecContext(ctx, `
		INSERT INTO templatesecret (template_id, key, value, created_at, updated_at)
		VALUES (?, ?, ?, ?, ?)
		ON CONFLICT(template_id, key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at`,
		templateID, name, value, now, now,
	)
	return err
}

// ListTemplateSecretKeys returns the secret names set for a template —
// never the values, so this is safe to expose from a read endpoint/MCP.
func (s *Store) ListTemplateSecretKeys(ctx context.Context, templateID int64) ([]string, error) {
	rows, err := s.DB.QueryContext(ctx, `
		SELECT key FROM templatesecret WHERE template_id = ? ORDER BY key`, templateID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := []string{}
	for rows.Next() {
		var k string
		if err := rows.Scan(&k); err != nil {
			return nil, err
		}
		out = append(out, k)
	}
	return out, rows.Err()
}

// DeleteTemplateSecret removes one key. No error when it didn't exist —
// DELETE is naturally idempotent here.
func (s *Store) DeleteTemplateSecret(ctx context.Context, templateID int64, name string) error {
	_, err := s.DB.ExecContext(ctx, `DELETE FROM templatesecret WHERE template_id = ? AND key = ?`, templateID, name)
	return err
}

// ResolveTemplateSecrets returns every secret for a template, keyed by
// name — the only caller is the emit_pool_command executor, which injects
// these into the child process env and nowhere else.
func (s *Store) ResolveTemplateSecrets(ctx context.Context, templateID int64) (map[string]string, error) {
	rows, err := s.DB.QueryContext(ctx, `
		SELECT key, value FROM templatesecret WHERE template_id = ?`, templateID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := map[string]string{}
	for rows.Next() {
		var k, v string
		if err := rows.Scan(&k, &v); err != nil {
			return nil, err
		}
		out[k] = v
	}
	return out, rows.Err()
}
