package health

import (
	"sync"
	"time"
)

const StaleAfter = 20.0

type Registry struct {
	mu   sync.Mutex
	seen map[string]heartbeat
}

type heartbeat struct {
	at     time.Time
	detail string
}

func New() *Registry {
	return &Registry{seen: map[string]heartbeat{}}
}

func (r *Registry) Record(component, detail string) {
	r.mu.Lock()
	defer r.mu.Unlock()
	r.seen[component] = heartbeat{at: time.Now().UTC(), detail: detail}
}

func (r *Registry) Snapshot() map[string]any {
	r.mu.Lock()
	defer r.mu.Unlock()
	now := time.Now().UTC()
	out := map[string]any{}
	for _, name := range []string{"overlay", "telegram"} {
		hb, ok := r.seen[name]
		comp := map[string]any{
			"status":       "offline",
			"age_seconds":  nil,
			"last_seen_at": nil,
			"detail":       "",
		}
		if ok {
			age := now.Sub(hb.at).Seconds()
			comp["detail"] = hb.detail
			comp["age_seconds"] = float64(int(age*10)) / 10 // one decimal-ish
			iso := hb.at.Format("2006-01-02T15:04:05Z")
			comp["last_seen_at"] = iso
			if age <= StaleAfter {
				comp["status"] = "ok"
			}
		}
		out[name] = comp
	}
	return out
}
