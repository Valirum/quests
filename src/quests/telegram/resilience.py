"""Retries for flaky Telegram API (proxy disconnects, etc.)."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import TypeVar

from aiogram.exceptions import (
    TelegramBadRequest,
    TelegramNetworkError,
    TelegramRetryAfter,
    TelegramServerError,
)

log = logging.getLogger("quests.telegram.resilience")

T = TypeVar("T")

_DEFAULT_ATTEMPTS = 5
_BASE_DELAY = 0.6


def _is_transient(exc: BaseException) -> bool:
    if isinstance(
        exc,
        (
            TelegramNetworkError,
            TelegramRetryAfter,
            TelegramServerError,
            ConnectionError,
            TimeoutError,
            asyncio.TimeoutError,
            OSError,
        ),
    ):
        return True
    return False


def _delay_for(exc: BaseException, attempt: int) -> float:
    if isinstance(exc, TelegramRetryAfter):
        return float(getattr(exc, "retry_after", _BASE_DELAY) or _BASE_DELAY)
    return min(12.0, _BASE_DELAY * (2**attempt))


async def tg_retry(
    op: Callable[[], Awaitable[T]],
    *,
    attempts: int = _DEFAULT_ATTEMPTS,
    label: str = "tg",
) -> T:
    """Run Telegram API call with exponential backoff on transient errors."""
    last: BaseException | None = None
    for i in range(max(1, attempts)):
        try:
            return await op()
        except Exception as e:
            if not _is_transient(e) or i + 1 >= attempts:
                raise
            last = e
            delay = _delay_for(e, i)
            log.warning(
                "%s transient (%s); retry in %.1fs (%s/%s)",
                label,
                e,
                delay,
                i + 1,
                attempts,
            )
            await asyncio.sleep(delay)
    assert last is not None
    raise last


async def tg_soft(
    op: Callable[[], Awaitable[T]],
    *,
    attempts: int = _DEFAULT_ATTEMPTS,
    label: str = "tg",
) -> T | None:
    """Like tg_retry, but swallow failure after retries (deletes, cleanup)."""
    try:
        return await tg_retry(op, attempts=attempts, label=label)
    except TelegramBadRequest:
        return None
    except Exception as e:
        log.warning("%s gave up after retries: %s", label, e)
        return None
