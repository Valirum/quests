"""Wayland ext-idle-notify-v1 helper (pywayland).

Major toasts wait for real seat activity before fading out.
Falls back gracefully when pywayland or the compositor protocol is missing.
"""

from __future__ import annotations

import logging
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from gi.repository import GLib

log = logging.getLogger("quests.overlay.idle")

_ACTIVE_PROBE_MS = 120
_AFK_MAX_MS = 15 * 60 * 1000

# Optional vendored wheel (overlay/_vendor) — .venv is often immutable in this env.
_VENDOR = Path(__file__).resolve().parent / "_vendor"
if _VENDOR.is_dir() and str(_VENDOR) not in sys.path:
    sys.path.insert(0, str(_VENDOR))

try:
    from pywayland.client import Display
    from pywayland.protocol.ext_idle_notify_v1 import (
        ExtIdleNotificationV1,
        ExtIdleNotifierV1,
    )
    from pywayland.protocol.wayland import WlRegistry, WlSeat

    _PYWAYLAND = True
except Exception as exc:  # noqa: BLE001 — optional dependency
    Display = None  # type: ignore[assignment,misc]
    ExtIdleNotificationV1 = None  # type: ignore[assignment,misc]
    ExtIdleNotifierV1 = None  # type: ignore[assignment,misc]
    WlRegistry = None  # type: ignore[assignment,misc]
    WlSeat = None  # type: ignore[assignment,misc]
    _PYWAYLAND = False
    log.info("idle-notify: pywayland unavailable (%s)", exc)


class IdleActivityMonitor:
    """Persistent Wayland idle connection; wait_for_activity() per toast."""

    def __init__(self) -> None:
        self._display: Any = None
        self._registry: Any = None
        self._seat: Any = None
        self._notifier: Any = None
        self._notifier_version = 0
        self._io_source: int | None = None
        self._globals: dict[str, tuple[int, int]] = {}
        self._notification: Any = None
        self._wait_token = 0
        self._on_active: Callable[[], None] | None = None
        self._saw_idled = False
        self._probe_source: int | None = None
        self._max_source: int | None = None

    @property
    def available(self) -> bool:
        return bool(self._display and self._seat and self._notifier)

    def start(self) -> bool:
        if self._display is not None:
            return self.available
        if not _PYWAYLAND:
            return False

        try:
            display = Display()
            display.connect()
        except Exception as exc:  # noqa: BLE001
            log.info("idle-notify: display connect failed: %s", exc)
            return False

        self._display = display
        self._globals.clear()

        def on_global(
            registry: Any,
            name: int,
            interface: str,
            version: int,
        ) -> None:
            self._globals[interface] = (int(name), int(version))

        def on_global_remove(registry: Any, name: int) -> None:
            return

        try:
            registry = display.get_registry()
            registry.dispatcher["global"] = on_global
            registry.dispatcher["global_remove"] = on_global_remove
            self._registry = registry
            display.roundtrip()

            seat_info = self._globals.get("wl_seat")
            notifier_info = self._globals.get("ext_idle_notifier_v1")
            if not seat_info or not notifier_info:
                log.info(
                    "idle-notify: missing globals (seat=%s notifier=%s)",
                    bool(seat_info),
                    bool(notifier_info),
                )
                self.stop()
                return False

            seat_name, seat_ver = seat_info
            not_name, not_ver = notifier_info
            bind_ver = min(2, not_ver)
            self._seat = registry.bind(seat_name, WlSeat, min(1, seat_ver))
            self._notifier = registry.bind(not_name, ExtIdleNotifierV1, bind_ver)
            self._notifier_version = bind_ver
            display.roundtrip()
        except Exception as exc:  # noqa: BLE001
            log.warning("idle-notify: setup failed: %s", exc)
            self.stop()
            return False

        fd = display.get_fd()

        def on_io(_fd: int, condition: int) -> bool:
            if self._display is None:
                return False
            if condition & (GLib.IO_ERR | GLib.IO_HUP):
                log.warning("idle-notify: wayland fd error")
                self.stop()
                return False
            try:
                self._display.read()
                self._display.dispatch(block=False)
                self._display.flush()
            except Exception as exc:  # noqa: BLE001
                log.warning("idle-notify: dispatch failed: %s", exc)
                self.stop()
                return False
            return True

        self._io_source = GLib.io_add_watch(
            fd, GLib.IO_IN | GLib.IO_ERR | GLib.IO_HUP, on_io
        )
        try:
            display.flush()
        except Exception:
            pass
        log.info(
            "idle-notify: ready (ext_idle_notifier_v1 v%s, input=%s)",
            self._notifier_version,
            self._notifier_version >= 2,
        )
        return True

    def stop(self) -> None:
        self._wait_token += 1
        self._on_active = None
        self._saw_idled = False
        for attr in ("_probe_source", "_max_source", "_io_source"):
            src = getattr(self, attr)
            if src is not None:
                try:
                    GLib.source_remove(src)
                except Exception:
                    pass
                setattr(self, attr, None)

        self._notification = None
        self._notifier = None
        self._seat = None
        self._registry = None
        display = self._display
        self._display = None
        if display is not None:
            try:
                display.disconnect()
            except Exception:
                pass
        self._globals.clear()

    def cancel_wait(self) -> None:
        self._wait_token += 1
        self._on_active = None
        self._saw_idled = False
        for attr in ("_probe_source", "_max_source"):
            src = getattr(self, attr)
            if src is not None:
                try:
                    GLib.source_remove(src)
                except Exception:
                    pass
                setattr(self, attr, None)

        notif = self._notification
        self._notification = None
        if notif is None:
            return

        def _destroy() -> bool:
            try:
                notif.destroy()
                if self._display is not None:
                    self._display.flush()
            except Exception:
                pass
            return False

        GLib.idle_add(_destroy)

    def wait_for_activity(
        self,
        on_active: Callable[[], None],
        *,
        probe_ms: int = _ACTIVE_PROBE_MS,
        max_afk_ms: int = _AFK_MAX_MS,
    ) -> bool:
        """Invoke on_active when the user is (or becomes) active.

        After a short probe: if compositor never sent ``idled``, the seat is
        currently active → fire immediately. If ``idled`` arrived, wait for
        ``resumed``. Returns False if idle-notify unavailable (caller should
        fall back to a timer).
        """
        if not self.available and not self.start():
            return False
        if self._notifier is None or self._seat is None:
            return False

        self.cancel_wait()
        token = self._wait_token
        self._on_active = on_active
        self._saw_idled = False

        def fire() -> None:
            if token != self._wait_token:
                return
            cb = self._on_active
            self._on_active = None
            self._wait_token += 1
            for attr in ("_probe_source", "_max_source"):
                src = getattr(self, attr)
                if src is not None:
                    try:
                        GLib.source_remove(src)
                    except Exception:
                        pass
                    setattr(self, attr, None)
            notif = self._notification
            self._notification = None

            def _run() -> bool:
                if notif is not None:
                    try:
                        notif.destroy()
                        if self._display is not None:
                            self._display.flush()
                    except Exception:
                        pass
                if cb is not None:
                    cb()
                return False

            GLib.idle_add(_run)

        def on_idled(_notification: Any) -> None:
            if token != self._wait_token:
                return
            self._saw_idled = True

        def on_resumed(_notification: Any) -> None:
            if token != self._wait_token:
                return
            fire()

        try:
            if self._notifier_version >= 2 and hasattr(
                self._notifier, "get_input_idle_notification"
            ):
                notification = self._notifier.get_input_idle_notification(0, self._seat)
            else:
                notification = self._notifier.get_idle_notification(0, self._seat)
        except Exception as exc:  # noqa: BLE001
            log.warning("idle-notify: create notification failed: %s", exc)
            return False

        self._notification = notification
        notification.dispatcher["idled"] = on_idled
        notification.dispatcher["resumed"] = on_resumed
        try:
            self._display.flush()
        except Exception:
            pass

        def probe() -> bool:
            if token != self._wait_token:
                return False
            if not self._saw_idled:
                fire()
            return False

        self._probe_source = GLib.timeout_add(max(1, int(probe_ms)), probe)

        def max_afk() -> bool:
            if token != self._wait_token:
                return False
            log.info("idle-notify: AFK max reached, dismissing")
            fire()
            return False

        self._max_source = GLib.timeout_add(max(1000, int(max_afk_ms)), max_afk)
        return True


_monitor: IdleActivityMonitor | None = None


def get_idle_monitor() -> IdleActivityMonitor:
    global _monitor
    if _monitor is None:
        _monitor = IdleActivityMonitor()
    return _monitor
