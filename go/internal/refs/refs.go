package refs

import (
	"regexp"
	"strconv"
)

// Kind IDs agents already paste: quest=23, note=12, …
var TokenRe = regexp.MustCompile(`\b(note|quest|questline|step|attachment)=(\d+)\b`)

type Ref struct {
	Kind string `json:"kind"`
	ID   int64  `json:"id"`
}

func Parse(text string) []Ref {
	if text == "" {
		return nil
	}
	seen := map[string]struct{}{}
	var out []Ref
	for _, m := range TokenRe.FindAllStringSubmatch(text, -1) {
		id, err := strconv.ParseInt(m[2], 10, 64)
		if err != nil || id <= 0 {
			continue
		}
		key := m[1] + "=" + m[2]
		if _, ok := seen[key]; ok {
			continue
		}
		seen[key] = struct{}{}
		out = append(out, Ref{Kind: m[1], ID: id})
	}
	return out
}

func FilterKind(list []Ref, kind string) []Ref {
	var out []Ref
	for _, r := range list {
		if r.Kind == kind {
			out = append(out, r)
		}
	}
	return out
}
