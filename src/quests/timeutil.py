"""Deadline / duration helpers. DB and API wire format: UTC."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

UTC = timezone.utc


def ensure_utc(dt: datetime | None) -> datetime | None:
    """Treat naive datetimes as UTC (SQLite round-trip); convert aware → UTC."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def to_db_utc(dt: datetime | None) -> datetime | None:
    """UTC wall time without tzinfo — what SQLite DateTime stores/returns."""
    dt = ensure_utc(dt)
    if dt is None:
        return None
    return dt.replace(tzinfo=None)


def to_utc_iso(dt: datetime | None) -> str | None:
    """RFC3339 UTC with trailing Z — safe for JS Date()."""
    dt = ensure_utc(dt)
    if dt is None:
        return None
    text = dt.isoformat(timespec="microseconds")
    # +00:00 → Z for clearer UTC signal to browsers
    if text.endswith("+00:00"):
        return text[:-6] + "Z"
    return text

# Default urgent window when deadline is set without an explicit duration.
DEFAULT_DURATION_SECONDS = 24 * 60 * 60


def auto_duration_seconds(deadline_at: datetime, anchor: datetime) -> int:
    """If duration omitted: 24h (or time left to deadline if shorter), at least 60s."""
    deadline_at = ensure_utc(deadline_at)
    anchor = ensure_utc(anchor)
    assert deadline_at is not None and anchor is not None
    left = int((deadline_at - anchor).total_seconds())
    if left <= 60:
        return 60
    return min(DEFAULT_DURATION_SECONDS, left)


def window_start(deadline_at: datetime, duration_seconds: int) -> datetime:
    deadline_at = ensure_utc(deadline_at)
    assert deadline_at is not None
    return deadline_at - timedelta(seconds=max(1, duration_seconds))


def is_in_urgent_window(
    deadline_at: datetime | None,
    duration_seconds: int | None,
    *,
    now: datetime | None = None,
) -> bool:
    """True when (deadline − duration) < now (urgent window has started)."""
    if deadline_at is None or not duration_seconds:
        return False
    now = ensure_utc(now or datetime.now(UTC))
    deadline_at = ensure_utc(deadline_at)
    assert now is not None and deadline_at is not None
    return window_start(deadline_at, duration_seconds) < now


def remaining_seconds(
    deadline_at: datetime | None,
    *,
    now: datetime | None = None,
) -> int | None:
    if deadline_at is None:
        return None
    now = ensure_utc(now or datetime.now(UTC))
    deadline_at = ensure_utc(deadline_at)
    assert now is not None and deadline_at is not None
    return int((deadline_at - now).total_seconds())


def timer_tone(
    deadline_at: datetime | None,
    duration_seconds: int | None,
    *,
    now: datetime | None = None,
) -> str | None:
    """green | orange | red — by remaining / duration fractions (2/3, 1/3)."""
    if deadline_at is None or not duration_seconds:
        return None
    rem = remaining_seconds(deadline_at, now=now)
    if rem is None:
        return None
    dur = max(1, int(duration_seconds))
    frac = rem / dur
    if frac > 2 / 3:
        return "green"
    if frac > 1 / 3:
        return "orange"
    return "red"


def format_remaining(seconds: int | None) -> str:
    if seconds is None:
        return ""
    sign = "-" if seconds < 0 else ""
    s = abs(int(seconds))
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    if h:
        return f"{sign}{h}:{m:02d}:{sec:02d}"
    return f"{sign}{m}:{sec:02d}"
