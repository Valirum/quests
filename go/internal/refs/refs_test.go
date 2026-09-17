package refs

import "testing"

func TestParseDedupesAndIgnoresJunk(t *testing.T) {
	got := Parse("see note=12 and quest=23; note=12 again, note=12a, attachment=4")
	if len(got) != 3 {
		t.Fatalf("len=%d got=%v", len(got), got)
	}
	want := []Ref{{"note", 12}, {"quest", 23}, {"attachment", 4}}
	for i := range want {
		if got[i] != want[i] {
			t.Fatalf("got=%v want=%v", got, want)
		}
	}
}

func TestParseDoesNotPrefixMatch(t *testing.T) {
	got := Parse("note=12 vs note=120")
	if len(got) != 2 || got[0].ID != 12 || got[1].ID != 120 {
		t.Fatalf("got=%v", got)
	}
}
