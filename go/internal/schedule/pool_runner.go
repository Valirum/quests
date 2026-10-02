package schedule

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"strconv"
	"sync"
	"time"

	"github.com/valirum/quests/go/internal/store"
)

// emitPoolInlineWait is how long a tick waits for a freshly started
// emit_pool_command before moving on: fast scripts still materialize in the
// same tick, slow ones are picked up by a later one instead of stalling the
// maintenance loop (expiry, window notices, step checks).
var emitPoolInlineWait = time.Second

// poolRunnerKeep bounds how long an unclaimed finished result is kept (a
// result whose period rolled over or whose command was edited is never read).
const poolRunnerKeep = 10 * time.Minute

type poolJob struct {
	done       chan struct{}
	items      []poolItem
	info       execInfo
	err        error
	finishedAt time.Time // set before done is closed
}

// poolRunner runs emit_pool_command off the maintenance loop: one job per
// (template, period, command), no duplicate runs while one is in flight, the
// result is handed out exactly once.
type poolRunner struct {
	mu   sync.Mutex
	jobs map[string]*poolJob
}

func newPoolRunner() *poolRunner {
	return &poolRunner{jobs: map[string]*poolJob{}}
}

func poolJobKey(templateID int64, periodKey, command string) string {
	sum := sha256.Sum256([]byte(command))
	return strconv.FormatInt(templateID, 10) + "|" + periodKey + "|" + hex.EncodeToString(sum[:8])
}

// exec returns the command's result once it is ready; ready=false means it is
// still running (the caller leaves the template alone this tick).
func (r *poolRunner) exec(ctx context.Context, st *store.Store, templateID int64, periodKey, command string) (items []poolItem, info execInfo, err error, ready bool) {
	key := poolJobKey(templateID, periodKey, command)

	r.mu.Lock()
	r.sweepLocked()
	job, running := r.jobs[key]
	if !running {
		job = &poolJob{done: make(chan struct{})}
		r.jobs[key] = job
		go func() {
			job.items, job.info, job.err = execEmitPoolCommand(ctx, st, templateID, command)
			job.finishedAt = time.Now()
			close(job.done)
		}()
	}
	r.mu.Unlock()

	if running {
		select {
		case <-job.done:
		default:
			return nil, execInfo{}, nil, false
		}
	} else {
		timer := time.NewTimer(emitPoolInlineWait)
		defer timer.Stop()
		select {
		case <-job.done:
		case <-timer.C:
			return nil, execInfo{}, nil, false
		}
	}

	r.mu.Lock()
	delete(r.jobs, key)
	r.mu.Unlock()
	return job.items, job.info, job.err, true
}

func (r *poolRunner) sweepLocked() {
	cutoff := time.Now().Add(-poolRunnerKeep)
	for k, j := range r.jobs {
		select {
		case <-j.done:
			if j.finishedAt.Before(cutoff) {
				delete(r.jobs, k)
			}
		default:
		}
	}
}
