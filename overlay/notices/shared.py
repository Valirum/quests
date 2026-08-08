"""Shared GTK helpers for notice hosts (major / minor / event log)."""

from __future__ import annotations

import cairo
from gi.repository import GLib, Gtk

from ..stylepacks import _load_pack, active_pack

SIGNIFICANCE_LABEL_RU = {
    "common": "обычное",
    "uncommon": "необычное",
    "epic": "эпическое",
    "legendary": "легендарное",
}


def pack_timing():
    mod = _load_pack(active_pack())
    return (
        getattr(mod, "MAJOR_FADE_IN_MS", 500),
        getattr(mod, "MAJOR_HOLD_MS", 1200),
        getattr(mod, "MAJOR_FADE_OUT_MS", 5000),
        getattr(mod, "MINOR_FADE_IN_MS", 280),
        getattr(mod, "MINOR_HOLD_MS", 3200),
        getattr(mod, "MINOR_FADE_OUT_MS", 400),
    )


def clear_box(box: Gtk.Box) -> None:
    child = box.get_first_child()
    while child is not None:
        box.remove(child)
        child = box.get_first_child()


def animate_opacity(
    widget: Gtk.Widget, start: float, end: float, duration_ms: int, done=None
):
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


def clickthrough(window: Gtk.Window) -> None:
    def on_realize(_w) -> None:
        surface = window.get_surface()
        if surface is not None:
            surface.set_input_region(cairo.Region())

    window.connect("realize", on_realize)
