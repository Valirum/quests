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


# Seed catalog (slug, label, sort_order).
# slug, label, sort_order, color (hex)
CATEGORY_SEED: list[tuple[str, str, int, str]] = [
    ("work", "Работа", 10, "#5a8a9a"),
    ("routine", "Рутина", 20, "#8a8578"),
    ("health", "Здоровье", 30, "#7a9e3a"),
    ("study", "Учёба", 40, "#6a7ab8"),
    ("fun", "Развлечения", 50, "#c47a20"),
]


class QuestCategory(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    slug: str = Field(max_length=32, unique=True, index=True)
    label: str = Field(max_length=64)
    sort_order: int = Field(default=0)
    # Accent hex for UI (sidebar / slider), e.g. "#5a8a9a".
    color: str = Field(default="#9a9a9a", max_length=16)
    created_at: datetime = Field(default_factory=utcnow)


class QuestCategoryRead(SQLModel):
    id: int
    slug: str
    label: str
    sort_order: int
    color: str


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
    # JSON object of attribute weights, e.g. {"str":1,"int":2}. Empty = XP+impulse only.
    reward_attrs: Optional[str] = Field(default=None, max_length=500)
    category_id: Optional[int] = Field(
        default=None, foreign_key="questcategory.id", index=True
    )
    questline_id: Optional[int] = Field(
        default=None, foreign_key="questline.id", index=True
    )


class QuestLineBase(SQLModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = ""
    category_id: Optional[int] = Field(
        default=None, foreign_key="questcategory.id", index=True
    )
    color: str = Field(default="#9a9a9a", max_length=16)
    icon: str = Field(default="document", max_length=32)


class QuestLine(QuestLineBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
    category: Optional[QuestCategory] = Relationship()


class QuestLineCreate(QuestLineBase):
    pass


class QuestLineUpdate(SQLModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = None
    category_id: Optional[int] = None
    color: Optional[str] = Field(default=None, max_length=16)
    icon: Optional[str] = Field(default=None, max_length=32)


class QuestLineRead(QuestLineBase):
    id: int
    created_at: datetime
    updated_at: datetime
    category_slug: Optional[str] = None
    category_label: Optional[str] = None
    category_color: Optional[str] = None

    @field_serializer("created_at", "updated_at", when_used="json")
    def _ser_utc(self, value: Optional[datetime]) -> Optional[str]:
        return to_utc_iso(value)


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
    category: Optional[QuestCategory] = Relationship()
    questline: Optional[QuestLine] = Relationship()


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
    reward_attrs: Optional[str] = Field(default=None, max_length=500)
    category_id: Optional[int] = None
    questline_id: Optional[int] = None
    steps: Optional[List[QuestStepCreate]] = None


class QuestRead(QuestBase):
    id: int
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None
    template_id: Optional[int] = None
    period_key: Optional[str] = None
    category_slug: Optional[str] = None
    category_label: Optional[str] = None
    category_color: Optional[str] = None
    questline_title: Optional[str] = None
    questline_color: Optional[str] = None
    questline_icon: Optional[str] = None
    steps: List[QuestStepRead] = Field(default_factory=list)
    steps_done: int = 0
    steps_total: int = 0
    progress_label: str = "0 / 0"
    # Derived timer fields (UTC-based; clients format for display).
    remaining_seconds: Optional[int] = None
    timer_tone: Optional[str] = None  # green | orange | red | overdue
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
    # JSON attribute weights copied onto instances, e.g. {"str":1,"int":2}.
    reward_attrs: Optional[str] = Field(default=None, max_length=500)
    category_id: Optional[int] = Field(
        default=None, foreign_key="questcategory.id", index=True
    )
    questline_id: Optional[int] = Field(
        default=None, foreign_key="questline.id", index=True
    )


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
    category: Optional[QuestCategory] = Relationship()
    questline: Optional[QuestLine] = Relationship()


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
    reward_attrs: Optional[str] = Field(default=None, max_length=500)
    category_id: Optional[int] = None
    questline_id: Optional[int] = None


class QuestTemplateRead(QuestTemplateBase):
    id: int
    created_at: datetime
    updated_at: datetime
    category_slug: Optional[str] = None
    category_label: Optional[str] = None
    category_color: Optional[str] = None
    questline_title: Optional[str] = None
    questline_color: Optional[str] = None
    questline_icon: Optional[str] = None
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


# --- Quest change log (append-only activity) ------------------------------


class QuestChangeLog(SQLModel, table=True):
    """Durable log of quest lifecycle / edits (not intra-step progress)."""

    id: Optional[int] = Field(default=None, primary_key=True)
    at: datetime = Field(default_factory=utcnow, index=True)
    kind: str = Field(max_length=32, index=True)
    quest_id: Optional[int] = Field(
        default=None,
        foreign_key="quest.id",
        index=True,
    )
    title: str = Field(default="", max_length=200)
    detail: str = Field(default="", max_length=500)
    significance: Optional[str] = Field(default=None, max_length=16)
    # Monotonic hub revision when published live; null if backfilled later.
    revision: Optional[int] = Field(default=None, index=True)


class QuestChangeLogRead(SQLModel):
    id: int
    at: datetime
    kind: str
    quest_id: Optional[int] = None
    title: str
    detail: str
    significance: Optional[str] = None
    revision: Optional[int] = None

    @field_serializer("at", when_used="json")
    def _ser_at(self, value: Optional[datetime]) -> Optional[str]:
        return to_utc_iso(value)


# --- Hero sheet / metrics -------------------------------------------------


class HeroAttributeId(str, Enum):
    str = "str"  # сила
    dex = "dex"  # ловкость
    con = "con"  # выносливость
    int = "int"  # интеллект
    wis = "wis"  # мудрость
    cha = "cha"  # харизма


ATTR_LABEL_RU: dict[str, str] = {
    HeroAttributeId.str.value: "Сила",
    HeroAttributeId.dex.value: "Ловкость",
    HeroAttributeId.con.value: "Выносливость",
    HeroAttributeId.int.value: "Интеллект",
    HeroAttributeId.wis.value: "Мудрость",
    HeroAttributeId.cha.value: "Харизма",
}


class HeroSheet(SQLModel, table=True):
    """Singleton player sheet (id=1)."""

    id: Optional[int] = Field(default=None, primary_key=True)
    xp: int = Field(default=0, ge=0)
    momentum: int = Field(default=50, ge=0, le=100)
    # Naive UTC; decay advances this by whole hours.
    momentum_updated_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class HeroAttribute(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("attr_id", name="uq_hero_attribute_attr_id"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    attr_id: str = Field(max_length=8, index=True)
    rank: int = Field(default=0, ge=0)
    progress: int = Field(default=0, ge=0)
    updated_at: datetime = Field(default_factory=utcnow)


class MetricLedger(SQLModel, table=True):
    """Append-only metric changes (xp / momentum / attribute progress)."""

    __table_args__ = (
        UniqueConstraint("quest_id", "reason", name="uq_metric_ledger_quest_reason"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    at: datetime = Field(default_factory=utcnow, index=True)
    kind: str = Field(max_length=16, index=True)  # xp | momentum | attr
    attr_id: Optional[str] = Field(default=None, max_length=8)
    delta: int = 0
    balance_after: int = 0
    quest_id: Optional[int] = Field(default=None, foreign_key="quest.id", index=True)
    reason: str = Field(max_length=64, index=True)
    flavor: Optional[str] = Field(default=None, max_length=300)


class HeroAttributeRead(SQLModel):
    attr_id: str
    label: str
    rank: int
    progress: int
    progress_to_next: int


class MetricLedgerRead(SQLModel):
    id: int
    at: datetime
    kind: str
    attr_id: Optional[str] = None
    delta: int
    balance_after: int
    quest_id: Optional[int] = None
    reason: str
    flavor: Optional[str] = None

    @field_serializer("at", when_used="json")
    def _ser_at(self, value: Optional[datetime]) -> Optional[str]:
        return to_utc_iso(value)


class HeroSheetRead(SQLModel):
    xp: int
    momentum: int
    momentum_updated_at: datetime
    updated_at: datetime
    attributes: List[HeroAttributeRead] = Field(default_factory=list)
    recent: List[MetricLedgerRead] = Field(default_factory=list)

    @field_serializer("momentum_updated_at", "updated_at", when_used="json")
    def _ser_utc(self, value: Optional[datetime]) -> Optional[str]:
        return to_utc_iso(value)
