"""Major (center) + minor (bottom-right) notice hosts."""

from __future__ import annotations

from collections import deque

import cairo
from gi.repository import Gdk, GLib, Gtk, Gtk4LayerShell as LayerShell

from .monitors import apply_monitor, list_monitors
from .sounds import sounds
from .stylepacks import _load_pack, active_pack


def _half_screen_width(window: Gtk.Window) -> int:
    mon = LayerShell.get_monitor(window)
    if mon is None:
        mons = list_monitors()
        mon = mons[0] if mons else None
    if mon is None:
        return 640
    return max(320, mon.get_geometry().width // 2)

MAJOR_KINDS = frozenset({"quest_created", "quest_completed", "quest_failed"})

MAJOR_EYEBROW = {
    "quest_created": "Получено задание",
    "quest_completed": "Задание завершено",
    "quest_failed": "Задание провалено",
}

MINOR_CHANGE = {
    "step_completed": "Шаг выполнен",
    "status_changed": "Статус изменён",
    "quest_deleted": "Удалено",
    "quest_delayed": "Задерживается",
    "step_progress": "Прогресс",
    "pin_changed": "Закрепление",
    "quest_updated": "Обновлено",
}


def _pack_timing():
    mod = _load_pack(active_pack())
    return (
        getattr(mod, "MAJOR_FADE_IN_MS", 500),
        getattr(mod, "MAJOR_HOLD_MS", 1200),
        getattr(mod, "MAJOR_FADE_OUT_MS", 5000),
        getattr(mod, "MINOR_FADE_IN_MS", 280),
        getattr(mod, "MINOR_HOLD_MS", 3200),
        getattr(mod, "MINOR_FADE_OUT_MS", 400),
    )


def _clear(box: Gtk.Box) -> None:
    child = box.get_first_child()
    while child is not None:
        box.remove(child)
        child = box.get_first_child()


def _animate_opacity(widget: Gtk.Widget, start: float, end: float, duration_ms: int, done=None):
    if duration_ms <= 0:
        widget.set_opacity(end)
        if done:
            done()
        return

    frames = max(1, duration_ms // 30)
    step = (end - start) / frames
    state = {"i": 0, "v": start}

    def tick() -> bool:
        state["i"] += 1
        state["v"] += step
        if state["i"] >= frames:
            widget.set_opacity(end)
            if done:
                done()
            return False
        widget.set_opacity(state["v"])
        return True

    widget.set_opacity(start)
    GLib.timeout_add(30, tick)


def _clickthrough(window: Gtk.Window) -> None:
    def on_realize(_w) -> None:
        surface = window.get_surface()
        if surface is not None:
            surface.set_input_region(cairo.Region())

    window.connect("realize", on_realize)


class MajorHost:
    def __init__(self, app: Gtk.Application) -> None:
        self._app = app
        self._queue: deque[dict] = deque()
        self._busy = False
        self._window = self._build()

    def _build(self) -> Gtk.ApplicationWindow:
        window = Gtk.ApplicationWindow(application=self._app, title="Quests Major")
        window.set_decorated(False)
        LayerShell.init_for_window(window)
        LayerShell.set_namespace(window, "quests-major")
        LayerShell.set_layer(window, LayerShell.Layer.OVERLAY)
        for edge in (
            LayerShell.Edge.TOP,
            LayerShell.Edge.BOTTOM,
            LayerShell.Edge.LEFT,
            LayerShell.Edge.RIGHT,
        ):
            LayerShell.set_anchor(window, edge, True)
        LayerShell.set_keyboard_mode(window, LayerShell.KeyboardMode.NONE)
        LayerShell.set_exclusive_zone(window, -1)

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        outer.add_css_class("notice-root")
        outer.set_hexpand(True)
        outer.set_vexpand(True)
        center = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        center.set_halign(Gtk.Align.CENTER)
        center.set_valign(Gtk.Align.CENTER)
        center.set_hexpand(True)
        center.set_vexpand(True)
        self._slot = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self._slot.set_halign(Gtk.Align.CENTER)
        center.append(self._slot)
        outer.append(center)
        window.set_child(outer)
        _clickthrough(window)
        return window

    def enqueue(self, event: dict) -> None:
        self._queue.append(event)
        self._pump()

    def _pump(self) -> None:
        if self._busy or not self._queue:
            return
        self._busy = True
        self._show(self._queue.popleft())

    def _show(self, event: dict) -> None:
        _clear(self._slot)
        kind = event.get("kind") or "quest_created"
        fade_in, hold, fade_out, *_ = _pack_timing()

        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        card.add_css_class("major")
        card.add_css_class(f"major--{kind}")
        card.set_halign(Gtk.Align.CENTER)
        card.set_opacity(0.0)
        half_w = _half_screen_width(self._window)

        def major_label(text: str, css_class: str, *, wrap: bool = False) -> Gtk.Label:
            lbl = Gtk.Label(label=text, xalign=0.5)
            lbl.set_halign(Gtk.Align.CENTER)
            lbl.set_justify(Gtk.Justification.CENTER)
            lbl.add_css_class(css_class)
            if wrap:
                lbl.set_wrap(True)
                lbl.set_size_request(half_w, -1)
            return lbl

        card.append(major_label(MAJOR_EYEBROW.get(kind, kind), "major__eyebrow"))
        card.append(major_label(event.get("title") or "—", "major__title", wrap=True))

        description = (event.get("description") or "").strip()
        if description:
            rule = Gtk.Box()
            rule.add_css_class("major__rule")
            rule.set_halign(Gtk.Align.CENTER)
            rule.set_size_request(half_w, 2)
            card.append(rule)
            card.append(major_label(description, "major__description", wrap=True))

        detail = (event.get("detail") or "").strip()
        if detail:
            card.append(major_label(detail, "major__detail", wrap=True))

        self._slot.append(card)
        self._window.present()
        sounds.play(event.get("sound") or kind, source="major")

        def after_in() -> None:
            def after_hold() -> bool:
                def after_out() -> None:
                    _clear(self._slot)
                    self._busy = False
                    if not self._queue:
                        self._window.hide()
                    else:
                        self._pump()

                _animate_opacity(card, 1.0, 0.0, fade_out, done=after_out)
                return False

            GLib.timeout_add(hold, after_hold)

        _animate_opacity(card, 0.0, 1.0, fade_in, done=after_in)


class MinorHost:
    def __init__(self, app: Gtk.Application) -> None:
        self._app = app
        self._queue: deque[dict] = deque()
        self._busy = False
        self._window = self._build()

    def _build(self) -> Gtk.ApplicationWindow:
        window = Gtk.ApplicationWindow(application=self._app, title="Quests Minor")
        window.set_decorated(False)
        window.set_default_size(320, -1)
        LayerShell.init_for_window(window)
        LayerShell.set_namespace(window, "quests-minor")
        LayerShell.set_layer(window, LayerShell.Layer.TOP)
        LayerShell.set_anchor(window, LayerShell.Edge.BOTTOM, True)
        LayerShell.set_anchor(window, LayerShell.Edge.RIGHT, True)
        LayerShell.set_margin(window, LayerShell.Edge.BOTTOM, 24)
        LayerShell.set_margin(window, LayerShell.Edge.RIGHT, 24)
        LayerShell.set_keyboard_mode(window, LayerShell.KeyboardMode.NONE)
        LayerShell.set_exclusive_zone(window, 0)

        self._slot = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        window.set_child(self._slot)
        _clickthrough(window)
        return window

    def enqueue(self, event: dict) -> None:
        self._queue.append(event)
        self._pump()

    def _pump(self) -> None:
        if self._busy or not self._queue:
            return
        self._busy = True
        self._show(self._queue.popleft())

    def _show(self, event: dict) -> None:
        _clear(self._slot)
        kind = event.get("kind") or "quest_updated"
        *_, fade_in, hold, fade_out = _pack_timing()

        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        card.add_css_class("minor")
        card.add_css_class(f"minor--{kind}")
        card.set_opacity(0.0)

        title = Gtk.Label(label=event.get("title") or "—", xalign=0)
        title.add_css_class("minor__title")
        title.set_wrap(True)
        change = Gtk.Label(
            label=MINOR_CHANGE.get(kind, kind.replace("_", " ")),
            xalign=0,
        )
        change.add_css_class("minor__change")
        card.append(title)
        card.append(change)

        detail = (event.get("detail") or "").strip()
        if detail:
            det = Gtk.Label(label=detail, xalign=0)
            det.add_css_class("minor__detail")
            det.set_wrap(True)
            card.append(det)

        self._slot.append(card)
        self._window.present()

        def after_in() -> None:
            def after_hold() -> bool:
                def after_out() -> None:
                    _clear(self._slot)
                    self._busy = False
                    if not self._queue:
                        self._window.hide()
                    else:
                        self._pump()

                _animate_opacity(card, 1.0, 0.0, fade_out, done=after_out)
                return False

            GLib.timeout_add(hold, after_hold)

        _animate_opacity(card, 0.0, 1.0, fade_in, done=after_in)


class NoticeRouter:
    """Split events into major / minor presentation lanes."""

    def __init__(self, app: Gtk.Application) -> None:
        self.major = MajorHost(app)
        self.minor = MinorHost(app)

    def set_monitor(self, monitor: Gdk.Monitor | None) -> None:
        apply_monitor(self.major._window, monitor)
        apply_monitor(self.minor._window, monitor)

    def enqueue(self, event: dict) -> None:
        kind = event.get("kind") or ""
        if event.get("toast") is False and kind not in MAJOR_KINDS:
            return
        if kind in MAJOR_KINDS:
            self.major.enqueue(event)
        else:
            # Quiet kinds stay off-screen unless explicitly toasted.
            if event.get("toast", True):
                self.minor.enqueue(event)
