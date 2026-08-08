"""Route domain events to major toast / minor toast / event log."""

from __future__ import annotations

from gi.repository import Gdk, GLib, Gtk

from ..hud.monitors import apply_monitor
from .event_log import MINOR_LOG_MAX, EventLogHost
from .major import MAJOR_KINDS, MajorHost
from .minor import MinorHost


class NoticeRouter:
    """Split events into major / minor presentation lanes."""

    def __init__(self, app: Gtk.Application) -> None:
        self.major = MajorHost(app)
        self.minor = MinorHost(app)
        self.log = EventLogHost(app)
        self.major_enabled = True
        self.minor_mode = "toast"  # off | toast | log
        self._log_refresh_pending = False

    def set_monitor(self, monitor: Gdk.Monitor | None) -> None:
        apply_monitor(self.major._window, monitor)
        apply_monitor(self.minor._window, monitor)
        apply_monitor(self.log._window, monitor)

    def set_enabled(
        self,
        *,
        major: bool | None = None,
        minor: bool | None = None,
        minor_mode: str | None = None,
    ) -> None:
        if major is not None:
            self.major_enabled = bool(major)
        # Prefer explicit mode; legacy ``minor`` bool maps to toast/off.
        if minor_mode is not None:
            mode = str(minor_mode).strip().lower()
            self.minor_mode = mode if mode in {"off", "toast", "log"} else "toast"
        elif minor is not None:
            self.minor_mode = "toast" if minor else "off"
        self._sync_minor_hosts()

    def set_minor_look(
        self,
        *,
        bg_mode: str | None = None,
        bg_alpha: float | None = None,
        text_alpha: float | None = None,
        width: int | None = None,
        height: int | None = None,
        line_mode: str | None = None,
        style_pack: str | None = None,
    ) -> None:
        self.log.set_look(
            bg_mode=bg_mode,
            bg_alpha=bg_alpha,
            text_alpha=text_alpha,
            width=width,
            height=height,
            line_mode=line_mode,
            style_pack=style_pack,
        )

    def refresh_log(self) -> None:
        """Pull durable /api/quest-log into the log panel (no-op unless mode=log)."""
        if self.minor_mode != "log":
            return
        try:
            from ..services.api_client import fetch_quest_log

            rows = fetch_quest_log(limit=MINOR_LOG_MAX)
        except Exception:
            return
        self.log.load_from_api(rows)

    def schedule_refresh_log(self, *, delay_ms: int = 200) -> None:
        """Debounced refresh after live events (DB write is async)."""
        if self.minor_mode != "log":
            return
        if self._log_refresh_pending:
            return
        self._log_refresh_pending = True

        def _go() -> bool:
            self._log_refresh_pending = False
            self.refresh_log()
            return False

        GLib.timeout_add(max(0, int(delay_ms)), _go)

    def _sync_minor_hosts(self) -> None:
        if self.minor_mode == "toast":
            self.log.hide()
        elif self.minor_mode == "log":
            self.minor.hide()
            self.refresh_log()
            self.log._window.present()
        else:
            self.minor.hide()
            self.log.hide()

    def enqueue(self, event: dict) -> None:
        kind = event.get("kind") or ""
        # Kinds that never land in QuestChangeLog — no panel refresh.
        log_skip = kind in {"step_progress", "startup", "quest_started"}
        if event.get("toast") is False and kind not in MAJOR_KINDS:
            if self.minor_mode == "log" and not log_skip:
                self.schedule_refresh_log()
            return
        if kind in MAJOR_KINDS:
            if self.major_enabled:
                self.major.enqueue(event)
            if self.minor_mode == "log":
                self.schedule_refresh_log()
            return
        if not event.get("toast", True):
            return
        if self.minor_mode == "toast":
            self.minor.enqueue(event)
        elif self.minor_mode == "log":
            self.schedule_refresh_log()
