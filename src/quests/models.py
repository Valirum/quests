from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional

from pydantic import field_serializer
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


class QuestBase(SQLModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = ""
    status: QuestStatus = QuestStatus.active
    pinned: bool = False
    sort_order: int = 0
    # Due instant (UTC). Null = no deadline.
    deadline_at: Optional[datetime] = None
    # Length of the countdown window ending at deadline_at (seconds).
    duration_seconds: Optional[int] = Field(default=None, ge=1)


class Quest(QuestBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
    completed_at: Optional[datetime] = None
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


class QuestStep(QuestStepBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    quest_id: Optional[int] = Field(default=None, foreign_key="quest.id", index=True)
    quest: Optional[Quest] = Relationship(back_populates="steps")

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


class QuestStepRead(QuestStepBase):
    id: int
    quest_id: int
    done: bool = False


class QuestCreate(QuestBase):
    steps: List[QuestStepCreate] = Field(default_factory=list)


class QuestUpdate(SQLModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = None
    status: Optional[QuestStatus] = None
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
