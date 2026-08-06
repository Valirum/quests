"""Telegram bot client for Quests (phone UI + push)."""

from __future__ import annotations

__all__ = ["run"]


def run() -> None:
    from quests.telegram.main import main

    main()
