package schedule

import (
	"bytes"
	"context"
	"log"
	"os"
	"os/exec"
	"regexp"
	"strconv"
	"strings"
	"sync"
	"time"

	"github.com/valirum/quests/go/internal/domain"
	"github.com/valirum/quests/go/internal/events"
	"github.com/valirum/quests/go/internal/store"
	"github.com/valirum/quests/go/internal/timeutil"
)

const (
	pollTimeout       = 60 * time.Second
	onceSafetyTimeout = 6 * time.Hour
	checkOutLimit     = 400
)

var intToken = regexp.MustCompile(`-?\d+`)

// CheckRunner executes step check_command (poll and one-shot) with linear wait_previous gating.
type CheckRunner struct {
	Store *store.Store
	Hub   *events.Hub

	mu       sync.Mutex
	inFlight map[int64]struct{}
	wg       sync.WaitGroup
}

func NewCheckRunner(st *store.Store, hub *events.Hub) *CheckRunner {
	return &CheckRunner{Store: st, Hub: hub, inFlight: map[int64]struct{}{}}
}

func (r *CheckRunner) tryLock(id int64) bool {
	r.mu.Lock()
	defer r.mu.Unlock()
	if _, ok := r.inFlight[id]; ok {
		return false
	}
	r.inFlight[id] = struct{}{}
	return true
}

func (r *CheckRunner) unlock(id int64) {
	r.mu.Lock()
	delete(r.inFlight, id)
	r.mu.Unlock()
}

func (r *CheckRunner) Wait() {
	r.wg.Wait()
}

// FailStaleRunning marks in-progress one-shots as failed after a server restart.
func (r *CheckRunner) FailStaleRunning(ctx context.Context) {
	active := domain.StatusActive
	quests, err := r.Store.ListQuests(ctx, store.ListFilter{Status: &active})
	if err != nil {
		log.Printf("checks: list stale: %v", err)
		return
	}
	now := timeutil.NowUTC()
	for _, q := range quests {
		for i := range q.Steps {
			st := q.Steps[i]
			if st.RunStatus == nil || *st.RunStatus != domain.RunRunning {
				continue
			}
			fail := domain.RunFail
			st.RunStatus = &fail
			st.CheckLastRunAt = &now
			qq := q
			qq.Status = domain.StatusFailed
			qq.UpdatedAt = now
			qq.CompletedAt = nil
			comment := "автошаг «" + st.Title + "»: прервано перезапуском сервера"
			updated, err := r.Store.UpdateStepComment(ctx, st, qq, "quest_failed", "провалено", comment)
			if err != nil {
				log.Printf("checks: stale fail step %d: %v", st.ID, err)
				continue
			}
			_ = r.Store.ApplyQuestStatusRewards(ctx, updated, domain.StatusFailed)
			qid := updated.ID
			r.Hub.Publish("quest_failed", events.PublishOpts{
				QuestID: &qid, Title: updated.Title, Description: updated.Description,
				Detail: "провалено", Toast: true, Source: "system",
				Significance: string(updated.Significance), StepTitle: st.Title,
				Automated: updated.Automated,
			})
		}
	}
}

func (r *CheckRunner) Tick(ctx context.Context) {
	active := domain.StatusActive
	quests, err := r.Store.ListQuests(ctx, store.ListFilter{Status: &active})
	if err != nil {
		log.Printf("checks: list: %v", err)
		return
	}
	now := timeutil.NowUTC()
	for _, q := range quests {
		for i := range q.Steps {
			st := q.Steps[i]
			if st.CheckCommand == nil || strings.TrimSpace(*st.CheckCommand) == "" || st.Done {
				continue
			}
			if st.WaitPrevious && i > 0 && !q.Steps[i-1].Done {
				continue
			}
			mode := st.RunMode
			if mode == "" {
				mode = domain.RunModePoll
			}
			if mode == domain.RunModeOnce {
				if st.RunStatus != nil {
					switch *st.RunStatus {
					case domain.RunRunning, domain.RunSuccess, domain.RunFail:
						continue
					}
				}
				r.spawn(ctx, q, st, true)
				continue
			}
			iv := 15
			if st.CheckIntervalSeconds != nil && *st.CheckIntervalSeconds >= 15 {
				iv = *st.CheckIntervalSeconds
			}
			if st.CheckLastRunAt != nil && now.Sub(*st.CheckLastRunAt) < time.Duration(iv)*time.Second {
				continue
			}
			r.spawn(ctx, q, st, false)
		}
	}
}

func (r *CheckRunner) spawn(ctx context.Context, q domain.Quest, st domain.Step, once bool) {
	if !r.tryLock(st.ID) {
		return
	}
	now := timeutil.NowUTC()
	st.CheckLastRunAt = &now
	if once {
		run := domain.RunRunning
		st.RunStatus = &run
	}
	if _, err := r.Store.UpdateStep(ctx, st, q, "step_progress", st.Title); err != nil {
		r.unlock(st.ID)
		log.Printf("checks: mark start step %d: %v", st.ID, err)
		return
	}
	if once {
		qid := q.ID
		r.Hub.Publish("step_auto_running", events.PublishOpts{
			QuestID: &qid, Title: q.Title, Detail: st.Title,
			Toast: true, Source: "system", Significance: string(q.Significance),
			StepTitle: st.Title, Automated: q.Automated,
		})
	}
	r.wg.Add(1)
	go func() {
		defer r.wg.Done()
		defer r.unlock(st.ID)
		r.exec(ctx, q.ID, st.ID, strings.TrimSpace(*st.CheckCommand), once)
	}()
}

func (r *CheckRunner) exec(parent context.Context, questID, stepID int64, command string, once bool) {
	timeout := pollTimeout
	if once {
		timeout = onceSafetyTimeout
	}
	ctx, cancel := context.WithTimeout(parent, timeout)
	defer cancel()

	cmd := exec.CommandContext(ctx, "sh", "-c", command)
	cmd.Env = os.Environ()
	if home, err := os.UserHomeDir(); err == nil {
		cmd.Dir = home
	}
	var stdout, stderr bytes.Buffer
	cmd.Stdout = &stdout
	cmd.Stderr = &stderr
	err := cmd.Run()
	out := stdout.String()
	errOut := stderr.String()
	exit := 0
	if err != nil {
		if ee, ok := err.(*exec.ExitError); ok {
			exit = ee.ExitCode()
		} else {
			exit = -1
		}
	}
	r.apply(parent, questID, stepID, once, exit, out, errOut, ctx.Err() == context.DeadlineExceeded)
}

func (r *CheckRunner) apply(ctx context.Context, questID, stepID int64, once bool, exit int, stdout, stderr string, timedOut bool) {
	q, err := r.Store.GetQuest(ctx, questID)
	if err != nil {
		log.Printf("checks: reload quest %d: %v", questID, err)
		return
	}
	var st *domain.Step
	for i := range q.Steps {
		if q.Steps[i].ID == stepID {
			st = &q.Steps[i]
			break
		}
	}
	if st == nil {
		return
	}
	now := timeutil.NowUTC()
	st.CheckLastRunAt = &now

	if once {
		r.applyOnce(ctx, q, st, exit, stdout, stderr, timedOut)
		return
	}
	if exit != 0 {
		_, _ = r.Store.UpdateStep(ctx, *st, q, "step_progress", st.Title)
		return
	}
	n, ok := ParseCheckStdout(stdout)
	if !ok {
		_, _ = r.Store.UpdateStep(ctx, *st, q, "step_progress", st.Title)
		return
	}
	if n < 0 {
		n = 0
	}
	if n > st.ProgressTotal {
		n = st.ProgressTotal
	}
	if n == st.ProgressCurrent {
		_, _ = r.Store.UpdateStep(ctx, *st, q, "step_progress", st.Title)
		return
	}
	st.ProgressCurrent = n
	domain.ClampStep(st)
	domain.SyncStatusFromSteps(&q, now)
	q.UpdatedAt = now
	kind := "step_progress"
	detail := st.Title
	toast := false
	if st.Done {
		kind = "step_completed"
		toast = true
	}
	if q.Status == domain.StatusCompleted {
		kind = "quest_completed"
		detail = "завершено"
		toast = true
	}
	updated, err := r.Store.UpdateStep(ctx, *st, q, kind, detail)
	if err != nil {
		log.Printf("checks: poll save step %d: %v", st.ID, err)
		return
	}
	if updated.Status == domain.StatusCompleted {
		_ = r.Store.ApplyQuestStatusRewards(ctx, updated, domain.StatusCompleted)
	}
	qid := updated.ID
	r.Hub.Publish(kind, events.PublishOpts{
		QuestID: &qid, Title: updated.Title, Description: updated.Description,
		Detail: detail, Toast: toast, Source: "system",
		Significance: string(updated.Significance), StepTitle: st.Title,
		Automated: updated.Automated,
	})
}

func (r *CheckRunner) applyOnce(ctx context.Context, q domain.Quest, st *domain.Step, exit int, stdout, stderr string, timedOut bool) {
	now := timeutil.NowUTC()
	st.CheckLastRunAt = &now
	if exit == 0 && !timedOut {
		ok := domain.RunSuccess
		st.RunStatus = &ok
		st.ProgressCurrent = st.ProgressTotal
		domain.ClampStep(st)
		domain.SyncStatusFromSteps(&q, now)
		q.UpdatedAt = now
		kind := "step_completed"
		detail := st.Title
		if q.Status == domain.StatusCompleted {
			kind = "quest_completed"
			detail = "завершено"
		}
		updated, err := r.Store.UpdateStep(ctx, *st, q, kind, detail)
		if err != nil {
			log.Printf("checks: once ok step %d: %v", st.ID, err)
			return
		}
		if updated.Status == domain.StatusCompleted {
			_ = r.Store.ApplyQuestStatusRewards(ctx, updated, domain.StatusCompleted)
		}
		qid := updated.ID
		r.Hub.Publish(kind, events.PublishOpts{
			QuestID: &qid, Title: updated.Title, Description: updated.Description,
			Detail: detail, Toast: true, Source: "system",
			Significance: string(updated.Significance), StepTitle: st.Title,
			Automated: updated.Automated,
		})
		return
	}

	fail := domain.RunFail
	st.RunStatus = &fail
	q.Status = domain.StatusFailed
	q.UpdatedAt = now
	q.CompletedAt = nil
	why := "код " + strconv.Itoa(exit)
	if timedOut {
		why = "таймаут"
	}
	comment := "автошаг «" + st.Title + "»: " + why
	if blob := trimCheckOut(stderr, stdout); blob != "" {
		comment += "\n" + blob
	}
	updated, err := r.Store.UpdateStepComment(ctx, *st, q, "quest_failed", "провалено", comment)
	if err != nil {
		log.Printf("checks: once fail step %d: %v", st.ID, err)
		return
	}
	_ = r.Store.ApplyQuestStatusRewards(ctx, updated, domain.StatusFailed)
	qid := updated.ID
	r.Hub.Publish("quest_failed", events.PublishOpts{
		QuestID: &qid, Title: updated.Title, Description: updated.Description,
		Detail: "провалено", Toast: true, Source: "system",
		Significance: string(updated.Significance), StepTitle: st.Title,
		Automated: updated.Automated,
	})
}

func trimCheckOut(stderr, stdout string) string {
	s := strings.TrimSpace(stderr)
	if s == "" {
		s = strings.TrimSpace(stdout)
	}
	s = strings.TrimSpace(s)
	if len(s) > checkOutLimit {
		s = s[:checkOutLimit] + "…"
	}
	return s
}

// ParseCheckStdout takes the last integer in command output (poll mode).
func ParseCheckStdout(out string) (int, bool) {
	s := strings.TrimSpace(out)
	if s == "" {
		return 0, false
	}
	lines := strings.Split(s, "\n")
	last := strings.TrimSpace(lines[len(lines)-1])
	if n, err := strconv.Atoi(last); err == nil {
		return n, true
	}
	toks := intToken.FindAllString(last, -1)
	if len(toks) == 0 {
		toks = intToken.FindAllString(s, -1)
	}
	if len(toks) == 0 {
		return 0, false
	}
	n, err := strconv.Atoi(toks[len(toks)-1])
	return n, err == nil
}
