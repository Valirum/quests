package domain

import "time"

type QuestStatus string

const (
	StatusActive    QuestStatus = "active"
	StatusDelayed   QuestStatus = "delayed"
	StatusCompleted QuestStatus = "completed"
	StatusFailed    QuestStatus = "failed"
	StatusArchived  QuestStatus = "archived"
)

type Significance string

const (
	SigCommon    Significance = "common"
	SigUncommon  Significance = "uncommon"
	SigEpic      Significance = "epic"
	SigLegendary Significance = "legendary"
)

type Category struct {
	ID        int64  `json:"id"`
	Slug      string `json:"slug"`
	Label     string `json:"label"`
	SortOrder int    `json:"sort_order"`
	Color     string `json:"color"`
}

type Step struct {
	ID                    int64      `json:"id"`
	QuestID               int64      `json:"quest_id"`
	Title                 string     `json:"title"`
	Description           string     `json:"description"`
	ProgressCurrent       int        `json:"progress_current"`
	ProgressTotal         int        `json:"progress_total"`
	SortOrder             int        `json:"sort_order"`
	CheckCommand          *string    `json:"check_command"`
	CheckIntervalSeconds  *int       `json:"check_interval_seconds"`
	CheckLastRunAt        *time.Time `json:"-"`
	Done                  bool       `json:"done"`
}

type Quest struct {
	ID              int64
	Title           string
	Description     string
	Status          QuestStatus
	Significance    Significance
	Pinned          bool
	SortOrder       int
	DeadlineAt      *time.Time
	DurationSeconds *int
	RewardAttrs     *string
	CategoryID      *int64
	QuestlineID     *int64
	CreatedAt       time.Time
	UpdatedAt       time.Time
	CompletedAt     *time.Time
	TemplateID      *int64
	PeriodKey       *string

	CategorySlug   *string
	CategoryLabel  *string
	CategoryColor  *string
	QuestlineTitle *string
	QuestlineColor *string
	QuestlineIcon  *string
	CustomIcon     *string
	QuestlineUpdatedAt *time.Time

	Steps []Step
}

type StepCreate struct {
	Title                string  `json:"title"`
	Description          string  `json:"description"`
	ProgressCurrent      int     `json:"progress_current"`
	ProgressTotal        int     `json:"progress_total"`
	SortOrder            *int    `json:"sort_order"`
	CheckCommand         *string `json:"check_command"`
	CheckIntervalSeconds *int    `json:"check_interval_seconds"`
}

type StepUpdate struct {
	Title                *string `json:"title"`
	Description          *string `json:"description"`
	ProgressCurrent      *int    `json:"progress_current"`
	ProgressTotal        *int    `json:"progress_total"`
	SortOrder            *int    `json:"sort_order"`
	CheckCommand         *string `json:"check_command"`
	CheckIntervalSeconds *int    `json:"check_interval_seconds"`
}

type QuestCreate struct {
	Title           string       `json:"title"`
	Description     string       `json:"description"`
	Status          QuestStatus  `json:"status"`
	Significance    Significance `json:"significance"`
	Pinned          bool         `json:"pinned"`
	SortOrder       int          `json:"sort_order"`
	DeadlineAt      *string      `json:"deadline_at"`
	DurationSeconds *int         `json:"duration_seconds"`
	RewardAttrs     *string      `json:"reward_attrs"`
	CategoryID      *int64       `json:"category_id"`
	QuestlineID     *int64       `json:"questline_id"`
	Steps           []StepCreate `json:"steps"`
}

func ClampStep(s *Step) {
	if s.ProgressTotal < 1 {
		s.ProgressTotal = 1
	}
	if s.ProgressCurrent < 0 {
		s.ProgressCurrent = 0
	}
	if s.ProgressCurrent > s.ProgressTotal {
		s.ProgressCurrent = s.ProgressTotal
	}
	s.Done = s.ProgressCurrent >= s.ProgressTotal
}

func SyncStatusFromSteps(q *Quest, now time.Time) {
	if len(q.Steps) == 0 {
		return
	}
	allDone := true
	for _, s := range q.Steps {
		if s.ProgressCurrent < s.ProgressTotal {
			allDone = false
			break
		}
	}
	if allDone && (q.Status == StatusActive || q.Status == StatusDelayed || q.Status == StatusFailed) {
		q.Status = StatusCompleted
	} else if !allDone && q.Status == StatusCompleted {
		q.Status = StatusActive
	}
	if q.Status == StatusCompleted && q.CompletedAt == nil {
		t := now
		q.CompletedAt = &t
	}
	if q.Status != StatusCompleted {
		q.CompletedAt = nil
	}
}

func ProgressLabel(steps []Step) (done, total int, label string) {
	if len(steps) == 0 {
		return 0, 0, "0 / 0"
	}
	if len(steps) == 1 {
		s := steps[0]
		d := 0
		if s.ProgressCurrent >= s.ProgressTotal {
			d = 1
		}
		return d, 1, itoa(s.ProgressCurrent) + " / " + itoa(s.ProgressTotal)
	}
	for _, s := range steps {
		total++
		if s.ProgressCurrent >= s.ProgressTotal {
			done++
		}
	}
	return done, total, itoa(done) + " / " + itoa(total)
}

func itoa(n int) string {
	if n == 0 {
		return "0"
	}
	var b [20]byte
	i := len(b)
	neg := n < 0
	if neg {
		n = -n
	}
	for n > 0 {
		i--
		b[i] = byte('0' + n%10)
		n /= 10
	}
	if neg {
		i--
		b[i] = '-'
	}
	return string(b[i:])
}
