#!/usr/bin/env python3
"""Quests overlay: pinned HUD + major/minor notices.

Requires: gtk4, gtk4-layer-shell, python-gobject
Optional: paplay/mpv for VO

Input mode (HUD):
  default = click-through (text chips only)
  interactive = panel + drag + monitor btn + titles; keys:
    Esc → passthrough · Space → monitor · arrows/hjkl → nudge
    Backspace / ─ → collapse (also exits interactive)
  toggle  = python -m overlay toggle
"""

from __future__ import annotations

import sys
import urllib.error
from ctypes import CDLL

CDLL("libgtk4-layer-shell.so")

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
gi.require_version("Gtk4LayerShell", "1.0")

from gi.repository import Gdk, GLib, Gtk, Gtk4LayerShell as LayerShell

from .api_client import fetch_events, fetch_quests
from .browser import focus_quest
from .drag import NUDGE_STEP, attach_drag_handle, nudge_hud
from .hud import MOCK_FAVORITES, MOCK_URGENT, build_hud, split_hud_quests
from .input_mode import apply_hud_input_mode
from .ipc import send_command, start_server, stop_server
from .monitors import apply_monitor, cycle_index, list_monitors, monitor_label
from .stylepacks import build_css
from .toast import NoticeRouter

APP_ID = "dev.quests.overlay"
NAMESPACE_HUD = "quests-overlay"
POLL_MS = 1200


def _cli(argv: list[str]) -> int:
    if not argv:
        return -1  # run daemon
    cmd = argv[0]
    if cmd in {"toggle", "toggle-input"}:
        print(send_command("toggle"))
        return 0
    if cmd in {"monitor", "next-monitor", "cycle-monitor"}:
        print(send_command("monitor"))
        return 0
    if cmd in {"interactive", "input"}:
        mode = argv[1] if len(argv) > 1 else "status"
        print(send_command(mode if mode in {"on", "off", "toggle", "status"} else "status"))
        return 0
    if cmd == "status":
        print(send_command("status"))
        return 0
    if cmd in {"-h", "--help", "help"}:
        print(
            "Usage:\n"
            "  python -m overlay              # start overlay daemon\n"
            "  python -m overlay toggle       # click-through ↔ interactive\n"
            "  python -m overlay monitor      # cycle output monitor\n"
            "  python -m overlay status\n"
            "  python -m overlay interactive on|off|toggle|status\n"
            "\n"
            "Interactive keys:\n"
            "  Esc  passthrough · Space  monitor · arrows/hjkl  move\n"
            "  Backspace  collapse HUD (passthrough)\n"
            "\n"
            "niri example:\n"
            '  Mod+Space { spawn-sh "python -m overlay toggle"; }\n'
            "  (run from Quests root or set PATH/PYTHONPATH)\n"
        )
        return 0
    print(f"Unknown command: {cmd}", file=sys.stderr)
    return 2


def on_activate(app: Gtk.Application) -> None:
    display = Gdk.Display.get_default()
    if display is not None:
        css = Gtk.CssProvider()
        css.load_from_string(build_css())
        Gtk.StyleContext.add_provider_for_display(
            display, css, Gtk.STYLE_PROVIDER_PRIORITY_USER
        )

    hud = Gtk.ApplicationWindow(application=app, title="Quests Overlay")
    hud.set_decorated(False)
    hud.set_default_size(340, -1)

    LayerShell.init_for_window(hud)
    LayerShell.set_namespace(hud, NAMESPACE_HUD)
    LayerShell.set_layer(hud, LayerShell.Layer.TOP)
    LayerShell.set_anchor(hud, LayerShell.Edge.TOP, True)
    LayerShell.set_anchor(hud, LayerShell.Edge.RIGHT, True)
    LayerShell.set_margin(hud, LayerShell.Edge.TOP, 24)
    LayerShell.set_margin(hud, LayerShell.Edge.RIGHT, 24)
    LayerShell.set_keyboard_mode(hud, LayerShell.KeyboardMode.NONE)

    notices = NoticeRouter(app)

    state: dict = {
        "revision": 0,
        "fingerprint": None,
        "interactive": False,
        "collapsed": False,
        "monitor_index": 0,
        "input_gen": 0,
        "dragging": False,
        "margin_top": 24,
        "margin_right": 24,
    }

    def apply_stored_margins() -> None:
        LayerShell.set_margin(hud, LayerShell.Edge.TOP, int(state["margin_top"]))
        LayerShell.set_margin(hud, LayerShell.Edge.RIGHT, int(state["margin_right"]))
        LayerShell.set_margin(hud, LayerShell.Edge.BOTTOM, 0)
        LayerShell.set_margin(hud, LayerShell.Edge.LEFT, 0)

    def remember_margins() -> None:
        state["margin_top"] = LayerShell.get_margin(hud, LayerShell.Edge.TOP)
        state["margin_right"] = LayerShell.get_margin(hud, LayerShell.Edge.RIGHT)

    def sync_monitor() -> str:
        mons = list_monitors(display)
        total = len(mons)
        if total == 0:
            apply_monitor(hud, None)
            notices.set_monitor(None)
            return "monitor: none"
        idx = state["monitor_index"] % total
        state["monitor_index"] = idx
        mon = mons[idx]
        apply_monitor(hud, mon)
        notices.set_monitor(mon)
        return f"monitor: {monitor_label(mon, idx, total)} ({idx + 1}/{total})"

    def sync_input_mode(*, gen: int | None = None) -> bool:
        if gen is not None and gen != state["input_gen"]:
            return False
        # Capture desired mode for this attempt (avoid off-by-one with late callbacks).
        apply_hud_input_mode(hud, bool(state["interactive"]))
        return False

    def schedule_input_sync() -> None:
        """Re-apply after layout/configure; invalidate older scheduled passes."""
        state["input_gen"] = int(state["input_gen"]) + 1
        gen = state["input_gen"]

        def pass_once() -> bool:
            return sync_input_mode(gen=gen)

        # Configure often runs after the first idle — stagger a few passes.
        GLib.idle_add(pass_once)
        GLib.timeout_add(16, pass_once)
        GLib.timeout_add(50, pass_once)
        GLib.timeout_add(120, pass_once)
        GLib.timeout_add(300, pass_once)

    def refresh_hud(*, force: bool = False) -> None:
        if state.get("dragging") and not force:
            return
        try:
            items = fetch_quests()
            favorites, urgent = split_hud_quests(items)
        except (urllib.error.URLError, TimeoutError, ValueError, TypeError, KeyError):
            favorites, urgent = MOCK_FAVORITES, MOCK_URGENT

        def _fp(block):
            return tuple(
                (
                    q.quest_id,
                    q.title,
                    q.timer_label,
                    q.timer_tone,
                    tuple((s.title, s.progress) for s in q.steps),
                )
                for q in block
            )

        fingerprint = (
            _fp(favorites),
            _fp(urgent),
            state["interactive"],
            state["collapsed"],
            state["monitor_index"],
        )
        if not force and fingerprint == state["fingerprint"]:
            return
        state["fingerprint"] = fingerprint

        def open_quest(quest_id: int) -> None:
            try:
                focus_quest(quest_id)
            except Exception:
                pass

        def on_hud_moved() -> None:
            remember_margins()

        def prepare_drag(handle: Gtk.Widget) -> None:
            attach_drag_handle(
                handle,
                window=hud,
                display=display,
                state=state,
                on_moved=on_hud_moved,
            )

        mons = list_monitors(display)
        total = len(mons)
        idx = state["monitor_index"] % total if total else 0
        mon = mons[idx] if total else None
        label = monitor_label(mon, idx, total)

        child, _hotspot = build_hud(
            favorites,
            urgent,
            interactive=state["interactive"],
            collapsed=state["collapsed"],
            monitor_label=label,
            on_cycle_monitor=cycle_monitor if state["interactive"] else None,
            on_toggle_collapsed=toggle_collapsed,
            on_prepare_drag_handle=prepare_drag if state["interactive"] else None,
            on_open_quest=open_quest,
        )
        if state["interactive"]:
            hud.add_css_class("hud-window--interactive")
        else:
            hud.remove_css_class("hud-window--interactive")
        if state["collapsed"]:
            hud.add_css_class("hud-window--collapsed")
        else:
            hud.remove_css_class("hud-window--collapsed")
        hud.set_child(child)
        apply_stored_margins()
        schedule_input_sync()

    def set_collapsed(collapsed: bool) -> str:
        state["collapsed"] = bool(collapsed)
        if state["collapsed"]:
            state["interactive"] = False
        refresh_hud(force=True)
        return "collapsed" if state["collapsed"] else "expanded"

    def toggle_collapsed() -> str:
        if state["collapsed"]:
            return set_collapsed(False)
        return set_collapsed(True)

    def set_interactive(enabled: bool) -> str:
        state["interactive"] = bool(enabled)
        if state["interactive"]:
            state["collapsed"] = False
        refresh_hud(force=True)
        if state["interactive"]:
            # Ensure layer-shell keyboard grab can land on this surface.
            hud.present()

            def _focus() -> bool:
                hud.grab_focus()
                return False

            GLib.idle_add(_focus)
        return "interactive" if state["interactive"] else "passthrough"

    def cycle_monitor() -> str:
        mons = list_monitors(display)
        state["monitor_index"] = cycle_index(state["monitor_index"], len(mons))
        result = sync_monitor()
        apply_stored_margins()
        refresh_hud(force=True)
        return result

    def on_key(
        _controller: Gtk.EventControllerKey,
        keyval: int,
        _keycode: int,
        _mods: int,
    ) -> bool:
        if not state["interactive"]:
            return False

        if keyval == Gdk.KEY_Escape:
            set_interactive(False)
            return True

        if keyval == Gdk.KEY_BackSpace:
            set_collapsed(True)
            return True

        if keyval in {Gdk.KEY_space, Gdk.KEY_KP_Space}:
            cycle_monitor()
            return True

        step = NUDGE_STEP
        dx = dy = 0
        if keyval in {Gdk.KEY_Left, Gdk.KEY_h, Gdk.KEY_H, Gdk.KEY_KP_Left}:
            dx = -step
        elif keyval in {Gdk.KEY_Right, Gdk.KEY_l, Gdk.KEY_L, Gdk.KEY_KP_Right}:
            dx = step
        elif keyval in {Gdk.KEY_Up, Gdk.KEY_k, Gdk.KEY_K, Gdk.KEY_KP_Up}:
            dy = -step
        elif keyval in {Gdk.KEY_Down, Gdk.KEY_j, Gdk.KEY_J, Gdk.KEY_KP_Down}:
            dy = step
        else:
            return False

        nudge_hud(
            hud,
            display,
            state,
            dx=dx,
            dy=dy,
            on_moved=remember_margins,
        )
        return True

    key_ctrl = Gtk.EventControllerKey()
    key_ctrl.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
    key_ctrl.connect("key-pressed", on_key)
    hud.add_controller(key_ctrl)
    hud.set_focusable(True)

    def ipc_handler(cmd: str) -> str:
        c = (cmd or "").strip().lower()
        if c in {"toggle", "toggle-input"}:
            return set_interactive(not state["interactive"])
        if c in {"on", "interactive", "interactive on"}:
            return set_interactive(True)
        if c in {"off", "passthrough", "interactive off"}:
            return set_interactive(False)
        if c in {"monitor", "next-monitor", "cycle-monitor"}:
            return cycle_monitor()
        if c in {"status", ""}:
            mons = list_monitors(display)
            total = len(mons)
            idx = state["monitor_index"] % total if total else 0
            mon = mons[idx] if total else None
            mode = "interactive" if state["interactive"] else "passthrough"
            fold = "collapsed" if state["collapsed"] else "expanded"
            return (
                f"{mode}; {fold}; "
                f"{monitor_label(mon, idx, total)} ({idx + 1}/{total})"
            )
        return f"error: unknown command '{cmd}'"

    def handle_events(events: list[dict]) -> None:
        if not events:
            return
        refresh_hud(force=True)
        for ev in events:
            notices.enqueue(ev)

    def poll() -> bool:
        try:
            revision, events = fetch_events(state["revision"])
        except (urllib.error.URLError, TimeoutError, ValueError, TypeError, KeyError):
            refresh_hud(force=False)
            return True

        if revision != state["revision"]:
            new_events = [e for e in events if int(e.get("revision", 0)) > state["revision"]]
            state["revision"] = revision
            if new_events:
                handle_events(new_events)
            else:
                refresh_hud(force=True)
        else:
            # Tick countdown labels even when no quest events arrived.
            refresh_hud(force=False)
        return True

    def on_realize(_w) -> None:
        sync_monitor()
        surface = hud.get_surface()
        if surface is not None:
            # Configure after CSS/child swap clears the region — stamp it again.
            surface.connect("notify::width", lambda *_: sync_input_mode())
            surface.connect("notify::height", lambda *_: sync_input_mode())
        schedule_input_sync()

    hud.connect("realize", on_realize)
    hud.connect("map", lambda _w: schedule_input_sync())

    sync_monitor()
    refresh_hud(force=True)
    try:
        revision, _ = fetch_events(0)
        state["revision"] = revision
    except (urllib.error.URLError, TimeoutError, ValueError, TypeError, KeyError):
        pass

    ipc_sock = start_server(ipc_handler)

    def on_shutdown(_app) -> None:
        stop_server(ipc_sock)

    app.connect("shutdown", on_shutdown)

    GLib.timeout_add(POLL_MS, poll)
    hud.present()
    schedule_input_sync()


def main(argv: list[str] | None = None) -> None:
    args = list(sys.argv[1:] if argv is None else argv)
    code = _cli(args)
    if code >= 0:
        raise SystemExit(code)

    app = Gtk.Application(application_id=APP_ID)
    app.connect("activate", on_activate)
    raise SystemExit(app.run(None))


if __name__ == "__main__":
    main()
