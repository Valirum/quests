"""Overlay support services: API, IPC, sounds, browser, idle."""

from .api_client import (
    API_BASE,
    fetch_categories,
    fetch_events,
    fetch_quest_log,
    fetch_quests,
    post_heartbeat,
)
from .browser import focus_quest
from .idle_notify import get_idle_monitor
from .ipc import send_command, start_server, stop_server
from .sounds import sounds

__all__ = [
    "API_BASE",
    "fetch_categories",
    "fetch_events",
    "fetch_quest_log",
    "fetch_quests",
    "focus_quest",
    "get_idle_monitor",
    "post_heartbeat",
    "send_command",
    "sounds",
    "start_server",
    "stop_server",
]
