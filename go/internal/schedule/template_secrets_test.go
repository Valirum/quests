package schedule

import (
	"context"
	"database/sql"
	"testing"

	_ "modernc.org/sqlite"

	"github.com/valirum/quests/go/internal/store"
)

const templateSecretsTestSchema = emitPoolSchema + `
CREATE TABLE templatesecret (
	id INTEGER PRIMARY KEY,
	template_id INTEGER NOT NULL,
	key TEXT NOT NULL,
	value TEXT NOT NULL,
	created_at DATETIME NOT NULL,
	updated_at DATETIME NOT NULL
);
CREATE UNIQUE INDEX ix_templatesecret_template_key ON templatesecret (template_id, key);
`

func openTemplateSecretsDB(t *testing.T) *store.Store {
	t.Helper()
	db, err := sql.Open("sqlite", "file:tmplsecrets_"+t.Name()+"?mode=memory&cache=shared")
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { _ = db.Close() })
	db.SetMaxOpenConns(1)
	if _, err := db.Exec(templateSecretsTestSchema); err != nil {
		t.Fatal(err)
	}
	return &store.Store{DB: db}
}

// TestExecEmitPoolCommandInjectsTemplateSecret proves the end-to-end path:
// a secret set via SetTemplateSecret shows up as an env var in the script's
// process, and nowhere else — this is the whole point of note=14/quest=199.
func TestExecEmitPoolCommandInjectsTemplateSecret(t *testing.T) {
	st := openTemplateSecretsDB(t)
	const templateID = int64(42)
	if err := st.SetTemplateSecret(context.Background(), templateID, "MY_SECRET", "hunter2"); err != nil {
		t.Fatalf("SetTemplateSecret: %v", err)
	}

	command := `#!/bin/sh
printf '[{"title":"%s","weight":1}]' "$MY_SECRET"
`
	items, _, err := execEmitPoolCommand(context.Background(), st, templateID, command)
	if err != nil {
		t.Fatalf("execEmitPoolCommand: %v", err)
	}
	if len(items) != 1 || items[0].Title != "hunter2" {
		t.Fatalf("want [{title:hunter2}], got %+v", items)
	}
}

// A template with no secrets set must not blow up — ResolveTemplateSecrets
// just returns an empty map and the env is unchanged. (An unset $MY_SECRET
// yields an empty title, which execEmitPoolCommand drops as a non-item —
// see materialize.go's blank-title filter — so the assertion is "no crash,
// no leaked pool item", not a literal empty-titled result.)
func TestExecEmitPoolCommandNoSecretsIsFine(t *testing.T) {
	st := openTemplateSecretsDB(t)
	const templateID = int64(7)

	command := `#!/bin/sh
printf '[{"title":"%s","weight":1}]' "$MY_SECRET"
`
	items, _, err := execEmitPoolCommand(context.Background(), st, templateID, command)
	if err != nil {
		t.Fatalf("execEmitPoolCommand: %v", err)
	}
	if len(items) != 0 {
		t.Fatalf("want no items (blank title dropped), got %+v", items)
	}
}

func TestTemplateSecretsNeverListValues(t *testing.T) {
	st := openTemplateSecretsDB(t)
	const templateID = int64(1)
	if err := st.SetTemplateSecret(context.Background(), templateID, "PASSWORD", "hunter2"); err != nil {
		t.Fatalf("SetTemplateSecret: %v", err)
	}

	keys, err := st.ListTemplateSecretKeys(context.Background(), templateID)
	if err != nil {
		t.Fatalf("ListTemplateSecretKeys: %v", err)
	}
	if len(keys) != 1 || keys[0] != "PASSWORD" {
		t.Fatalf("want [PASSWORD], got %v", keys)
	}

	if err := st.DeleteTemplateSecret(context.Background(), templateID, "PASSWORD"); err != nil {
		t.Fatalf("DeleteTemplateSecret: %v", err)
	}
	resolved, err := st.ResolveTemplateSecrets(context.Background(), templateID)
	if err != nil {
		t.Fatalf("ResolveTemplateSecrets: %v", err)
	}
	if len(resolved) != 0 {
		t.Fatalf("want no secrets after delete, got %v", resolved)
	}
}
