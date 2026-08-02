from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional

from pydantic import field_serializer
from sqlalchemy import UniqueConstraint
from sqlmodel import Field, Relationship, SQLModel

from quests.timeutil import to_db_utc, to_utc_iso


def utcnow() -> datetime:
    """Naive UTC for DB columns (SQLite has no timezone)."""
    now = to_db_utc(datetime.now(timezone.utc))
    assert now is not None
    return now


class QuestStatus(str, Enum):
    """Lifecycle status. Extensible later (delayed = real-life slip, not fail)."""

    active = "active"
    delayed = "delayed"
    completed = "completed"
    failed = "failed"
    archived = "archived"


class TemplateFreq(str, Enum):
    daily = "daily"
    weekly = "weekly"


class TemplateEmitMode(str, Enum):
    """How a due template becomes a quest instance."""

    fixed = "fixed"  # appear at start of period (current behaviour)
    surprise = "surprise"  # chance + random time within window


class TemplateEmitOutcome(str, Enum):
    miss = "miss"
    scheduled = "scheduled"
    materialized = "materialized"


class QuestSignificance(str, Enum):
    """Game-style rarity (not priority)."""

    common = "common"  # обычное
    uncommon = "uncommon"  # необычное
    epic = "epic"  # эпическое
    legendary = "legendary"  # легендарное


SIGNIFICANCE_LABEL_RU: dict[str, str] = {
    QuestSignificance.common.value: "обычное",
    QuestSignificance.uncommon.value: "необычное",
    QuestSignificance.epic.value: "эпическое",
    QuestSignificance.legendary.value: "легендарное",
}


class QuestBase(SQLModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = ""
    status: QuestStatus = QuestStatus.active
    significance: QuestSignificance = QuestSignificance.common
    pinned: bool = False
    sort_order: int = 0
    # Due instant (UTC). Null = no deadline.
    deadline_at: Optional[datetime] = None
    # Length of the countdown window ending at deadline_at (seconds).
    duration_seconds: Optional[int] = Field(default=None, ge=1)


class Quest(QuestBase, table=True):
    __table_args__ = (
        UniqueConstraint("template_id", "period_key", name="uq_quest_template_period"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
    completed_at: Optional[datetime] = None
    template_id: Optional[int] = Field(
        default=None, foreign_key="questtemplate.id", index=True
    )
    period_key: Optional[str] = Field(default=None, max_length=32, index=True)
    steps: List["QuestStep"] = Relationship(
        back_populates="quest",
        sa_relationship_kwargs={
            "cascade": "all, delete-orphan",
            "order_by": "QuestStep.sort_order",
        },
    )


class QuestStepBase(SQLModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = ""
    # Binary step: total=1, current 0|1. Quantified: e.g. 5/8 herbs.
    progress_current: int = Field(default=0, ge=0)
    progress_total: int = Field(default=1, ge=1)
    sort_order: int = 0
    # Optional shell check: stdout → progress_current, polled every N seconds.
    check_command: Optional[str] = Field(default=None, max_length=2000)
    check_interval_seconds: Optional[int] = Field(default=None, ge=15)


class QuestStep(QuestStepBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    quest_id: Optional[int] = Field(default=None, foreign_key="quest.id", index=True)
    quest: Optional[Quest] = Relationship(back_populates="steps")
    # Last successful/attempted auto-check (UTC naive).
    check_last_run_at: Optional[datetime] = None

    @property
    def done(self) -> bool:
        return self.progress_current >= self.progress_total


class QuestStepCreate(QuestStepBase):
    pass


class QuestStepUpdate(SQLModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = None
    progress_current: Optional[int] = Field(default=None, ge=0)
    progress_total: Optional[int] = Field(default=None, ge=1)
    sort_order: Optional[int] = None
    check_command: Optional[str] = Field(default=None, max_length=2000)
    check_interval_seconds: Optional[int] = Field(default=None, ge=15)


class QuestStepRead(QuestStepBase):
    id: int
    quest_id: int
    done: bool = False
    check_last_run_at: Optional[datetime] = None

    @field_serializer("check_last_run_at", when_used="json")
    def _ser_check_last(self, value: Optional[datetime]) -> Optional[str]:
        return to_utc_iso(value)


class QuestCreate(QuestBase):
    steps: List[QuestStepCreate] = Field(default_factory=list)


class QuestUpdate(SQLModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = None
    status: Optional[QuestStatus] = None
    significance: Optional[QuestSignificance] = None
    pinned: Optional[bool] = None
    sort_order: Optional[int] = None
    deadline_at: Optional[datetime] = None
    duration_seconds: Optional[int] = Field(default=None, ge=1)
    steps: Optional[List[QuestStepCreate]] = None


class QuestRead(QuestBase):
    id: int
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None
    template_id: Optional[int] = None
    period_key: Optional[str] = None
    steps: List[QuestStepRead] = Field(default_factory=list)
    steps_done: int = 0
    steps_total: int = 0
    progress_label: str = "0 / 0"
    # Derived timer fields (UTC-based; clients format for display).
    remaining_seconds: Optional[int] = None
    timer_tone: Optional[str] = None  # green | orange | red
    urgent: bool = False

    @field_serializer(
        "created_at",
        "updated_at",
        "completed_at",
        "deadline_at",
        when_used="json",
    )
    def _ser_utc(self, value: Optional[datetime]) -> Optional[str]:
        return to_utc_iso(value)


# --- Periodic templates -------------------------------------------------


class QuestTemplateBase(SQLModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = ""
    pinned: bool = False
    significance: QuestSignificance = QuestSignificance.common
    sort_order: int = 0
    # Local time-of-day for instance deadline ("HH:MM"). Null = no deadline.
    # Ignored when emit_mode=surprise (deadline = appear + duration_seconds).
    deadline_time: Optional[str] = Field(default=None, max_length=8)
    duration_seconds: Optional[int] = Field(default=None, ge=1)
    freq: TemplateFreq = TemplateFreq.daily
    # Comma-separated Mon=0 … Sun=6 (Python weekday). Used when freq=weekly.
    weekdays: str = Field(default="0,1,2,3,4,5,6", max_length=32)
    enabled: bool = True
    timezone: str = Field(default="Europe/Moscow", max_length=64)
    emit_mode: TemplateEmitMode = TemplateEmitMode.fixed
    # Probability of appearing in the period (surprise only). 0..1
    emit_chance: float = Field(default=1.0, ge=0.0, le=1.0)
    # Local window for random scheduled_at ("HH:MM"). Empty → 00:00..23:59.
    emit_window_start: Optional[str] = Field(default=None, max_length=8)
    emit_window_end: Optional[str] = Field(default=None, max_length=8)


class QuestTemplate(QuestTemplateBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
    steps: List["QuestTemplateStep"] = Relationship(
        back_populates="template",
        sa_relationship_kwargs={
            "cascade": "all, delete-orphan",
            "order_by": "QuestTemplateStep.sort_order",
        },
    )


class QuestTemplateStepBase(SQLModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = ""
    # Inclusive range; materialize picks uniform progress_total in [min, max].
    progress_min: int = Field(default=1, ge=1)
    progress_max: int = Field(default=1, ge=1)
    sort_order: int = 0
    check_command: Optional[str] = Field(default=None, max_length=2000)
    check_interval_seconds: Optional[int] = Field(default=None, ge=15)


class QuestTemplateStep(QuestTemplateStepBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    template_id: Optional[int] = Field(
        default=None, foreign_key="questtemplate.id", index=True
    )
    template: Optional[QuestTemplate] = Relationship(back_populates="steps")


class QuestTemplateStepCreate(SQLModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = ""
    progress_min: Optional[int] = Field(default=None, ge=1)
    progress_max: Optional[int] = Field(default=None, ge=1)
    # Shorthand: sets min = max = progress_total when range omitted.
    progress_total: Optional[int] = Field(default=None, ge=1)
    sort_order: int = 0
    check_command: Optional[str] = Field(default=None, max_length=2000)
    check_interval_seconds: Optional[int] = Field(default=None, ge=15)


class QuestTemplateStepRead(QuestTemplateStepBase):
    id: int
    template_id: int


class QuestTemplateCreate(QuestTemplateBase):
    steps: List[QuestTemplateStepCreate] = Field(default_factory=list)


class QuestTemplateUpdate(SQLModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = None
    pinned: Optional[bool] = None
    significance: Optional[QuestSignificance] = None
    sort_order: Optional[int] = None
    duration_seconds: Optional[int] = Field(default=None, ge=1)
    deadline_time: Optional[str] = Field(default=None, max_length=8)
    freq: Optional[TemplateFreq] = None
    weekdays: Optional[str] = Field(default=None, max_length=32)
    enabled: Optional[bool] = None
    timezone: Optional[str] = Field(default=None, max_length=64)
    emit_mode: Optional[TemplateEmitMode] = None
    emit_chance: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    emit_window_start: Optional[str] = Field(default=None, max_length=8)
    emit_window_end: Optional[str] = Field(default=None, max_length=8)
    steps: Optional[List[QuestTemplateStepCreate]] = None


class QuestTemplateRead(QuestTemplateBase):
    id: int
    created_at: datetime
    updated_at: datetime
    steps: List[QuestTemplateStepRead] = Field(default_factory=list)

    @field_serializer("created_at", "updated_at", when_used="json")
    def _ser_utc(self, value: Optional[datetime]) -> Optional[str]:
        return to_utc_iso(value)


class TemplateEmitRoll(SQLModel, table=True):
    """One surprise roll per template period (miss / wait / done)."""

    __table_args__ = (
        UniqueConstraint(
            "template_id", "period_key", name="uq_template_emit_roll_period"
        ),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    template_id: int = Field(foreign_key="questtemplate.id", index=True)
    period_key: str = Field(max_length=32, index=True)
    outcome: TemplateEmitOutcome = TemplateEmitOutcome.miss
    # UTC naive; set when outcome=scheduled (and kept after materialize).
    scheduled_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
