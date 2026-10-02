package db

import "testing"

// Deliberately failing: exercises the CI red path (promote/deploy must be skipped
// and :main must not move). Reverted in the next commit.
func TestCIRedPath(t *testing.T) {
	t.Fatal("intentional failure to verify CI gating")
}
