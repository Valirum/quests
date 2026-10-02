package db

import (
	"os"
	"path/filepath"
	"regexp"
	"testing"
)

// TestExpectedAlembicIsHead keeps expectedAlembic/alembicOrder in step with
// the migrations in alembic/versions: forgetting to bump them makes a freshly
// migrated DB look "ahead of the binary" in the health probe.
func TestExpectedAlembicIsHead(t *testing.T) {
	files, err := filepath.Glob("../../../alembic/versions/*.py")
	if err != nil || len(files) == 0 {
		t.Skip("alembic/versions not found")
	}
	revRe := regexp.MustCompile(`(?m)^revision(?:: str)? = ["']([0-9a-f]+)["']`)
	downRe := regexp.MustCompile(`(?m)^down_revision(?:: [^=]+)? = ["']([0-9a-f]+)["']`)
	revs := map[string]bool{}
	downs := map[string]bool{}
	for _, f := range files {
		b, err := os.ReadFile(f)
		if err != nil {
			t.Fatal(err)
		}
		if m := revRe.FindSubmatch(b); m != nil {
			revs[string(m[1])] = true
		}
		if m := downRe.FindSubmatch(b); m != nil {
			downs[string(m[1])] = true
		}
	}
	var heads []string
	for r := range revs {
		if !downs[r] {
			heads = append(heads, r)
		}
	}
	if len(heads) != 1 || heads[0] != expectedAlembic {
		t.Fatalf("alembic heads = %v, expectedAlembic = %s", heads, expectedAlembic)
	}
	if alembicOrder[len(alembicOrder)-1] != expectedAlembic {
		t.Fatalf("alembicOrder must end with expectedAlembic")
	}
	for r := range revs {
		found := false
		for _, o := range alembicOrder {
			found = found || o == r
		}
		if !found {
			t.Errorf("revision %s missing from alembicOrder", r)
		}
	}
}
