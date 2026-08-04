#!/usr/bin/env python3
"""Quests overlay: pinned HUD + major/minor notices.

Requires: gtk4, gtk4-layer-shell, python-gobject
Optional: paplay/mpv for VO

Input mode (HUD):
  default = click-through (text chips only)
  interactive = panel + drag + gear settings + titles; keys:
    Esc → passthrough · Space → monitor · arrows/hjkl → nudge
    Backspace / − → collapse (also exits interactive)
  gear → settings panel (monitors / style / bg / alpha); list icon → quests
  toggle  = python -m overlay toggle
  Settings: data/overlay.json (style, monitor, margins, passthrough bg)
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
from . import config as overlay_config
from .drag import NUDGE_STEP, attach_drag_handle, nudge_hud
from .hud import (
    apply_timer_bindings,
    build_hud,
    split_hud_quests,
)
from .input_mode import apply_hud_input_mode
from .ipc import send_command, start_server, stop_server
from .monitors import (
    apply_monitor,
    cycle_index,
    list_monitors,
    monitor_connector,
    monitor_label,
    resolve_monitor_index,
)
from .stylepacks import apply_style_pack, build_css, build_passthrough_css, list_packs
from .toast import NoticeRouter

APP_ID = "dev.quests.overlay"
NAMESPACE_HUD = "quests-overlay"
# Live event poll (no HUD rebuild unless revision changes).
EVENT_POLL_MS = 2500
# Countdown chips update in place.
TIMER_TICK_MS = 1000
# Soft full re-fetch for missed events / urgent window shifts.
DATA_SYNC_MS = 15000


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
    if cmd == "style":
        arg = argv[1] if len(argv) > 1 else "status"
        print(send_command("style" if arg in {"status", "list"} else f"style {arg}"))
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
            "  python -m overlay style [name] # show / set style pack\n"
            "  python -m overlay status\n"
            "  python -m overlay interactive on|off|toggle|status\n"
            "\n"
            "Interactive keys:\n"
            "  Esc  passthrough · Space  monitor · arrows/hjkl  move\n"
            "  Backspace  collapse HUD (passthrough)\n"
            "\n"
            "Settings: data/overlay.json (style, monitor, margins, passthrough bg)\n"
            "\n"
            "niri example:\n"
            '  Mod+Space { spawn-sh "python -m overlay toggle"; }\n'
            "  (run from Quests root or set PATH/PYTHONPATH)\n"
        )
        return 0
    print(f"Unknown command: {cmd}", file=sys.stderr)
    return 2


def on_activate(app: Gtk.Application) -> None:
    saved = overlay_config.load()

    display = Gdk.Display.get_default()
    css_provider = Gtk.CssProvider()
    passthrough_css = Gtk.CssProvider()
    pack_id = apply_style_pack(str(saved.get("style_pack") or "fantasy"), reload=False)
    if display is not None:
        css_provider.load_from_string(build_css())
        Gtk.StyleContext.add_provider_for_display(
            display, css_provider, Gtk.STYLE_PROVIDER_PRIORITY_USER
        )
        # After pack CSS so passthrough look overrides chip/panel defaults.
        Gtk.StyleContext.add_provider_for_display(
            display, passthrough_css, Gtk.STYLE_PROVIDER_PRIORITY_USER
        )

    hud = Gtk.ApplicationWindow(application=app, title="Quests Overlay")
    hud.set_decorated(False)
    hud.set_default_size(340, -1)

    LayerShell.init_for_window(hud)
    LayerShell.set_namespace(hud, NAMESPACE_HUD)
    LayerShell.set_layer(hud, LayerShell.Layer.TOP)
    LayerShell.set_anchor(hud, LayerShell.Edge.TOP, True)
    LayerShell.set_anchor(hud, LayerShell.Edge.RIGHT, True)
    LayerShell.set_margin(hud, LayerShell.Edge.TOP, int(saved.get("margin_top", 24)))
    LayerShell.set_margin(hud, LayerShell.Edge.RIGHT, int(saved.get("margin_right", 24)))
    LayerShell.set_keyboard_mode(hud, LayerShell.KeyboardMode.NONE)

    notices = NoticeRouter(app)

    state: dict = {
        "revision": 0,
        "fingerprint": None,
        "interactive": False,
        "collapsed": False,
        "monitor_index": int(saved.get("monitor_index") or 0),
        "monitor_connector": str(saved.get("monitor_connector") or ""),
        "style_pack": pack_id,
        "passthrough_bg_mode": str(saved.get("passthrough_bg_mode") or "chips"),
        "passthrough_bg_alpha": float(saved.get("passthrough_bg_alpha", 0.6)),
        "toasts_major": bool(saved.get("toasts_major", True)),
        "toasts_minor": bool(saved.get("toasts_minor", True)),
        "input_gen": 0,
        "dragging": False,
        "margin_top": int(saved.get("margin_top", 24)),
        "margin_right": int(saved.get("margin_right", 24)),
        "timer_bindings": [],
        "settings_open": False,
        "pending_refresh": False,
        "sync_ticks": 0,
    }

    def persist() -> None:
        mons = list_monitors(display)
        idx = state["monitor_index"] % len(mons) if mons else 0
        mon = mons[idx] if mons else None
        conn = monitor_connector(mon) or str(state.get("monitor_connector") or "")
        overlay_config.save(
            {
                "style_pack": state["style_pack"],
                "monitor_index": idx,
                "monitor_connector": conn,
                "margin_top": int(state["margin_top"]),
                "margin_right": int(state["margin_right"]),
                "passthrough_bg_mode": state["passthrough_bg_mode"],
                "passthrough_bg_alpha": state["passthrough_bg_alpha"],
                "toasts_major": bool(state["toasts_major"]),
                "toasts_minor": bool(state["toasts_minor"]),
            }
        )

    def apply_passthrough_look() -> None:
        alpha_raw = state.get("passthrough_bg_alpha", 0.6)
        try:
            alpha = max(0.0, min(1.0, float(alpha_raw)))
        except (TypeError, ValueError):
            alpha = 0.6
        passthrough_css.load_from_string(
            build_passthrough_css(
                mode=str(state.get("passthrough_bg_mode") or "chips"),
                alpha=alpha,
                name=str(state.get("style_pack") or pack_id),
            )
        )

    def reload_css() -> None:
        css_provider.load_from_string(build_css())
        apply_passthrough_look()

    def apply_stored_margins() -> None:
        LayerShell.set_margin(hud, LayerShell.Edge.TOP, int(state["margin_top"]))
        LayerShell.set_margin(hud, LayerShell.Edge.RIGHT, int(state["margin_right"]))
        LayerShell.set_margin(hud, LayerShell.Edge.BOTTOM, 0)
        LayerShell.set_margin(hud, LayerShell.Edge.LEFT, 0)

    def remember_margins() -> None:
        state["margin_top"] = LayerShell.get_margin(hud, LayerShell.Edge.TOP)
        state["margin_right"] = LayerShell.get_margin(hud, LayerShell.Edge.RIGHT)
        persist()

    def sync_monitor() -> str:
        mons = list_monitors(display)
        total = len(mons)
        if total == 0:
            apply_monitor(hud, None)
            notices.set_monitor(None)
            return "monitor: none"
        idx = resolve_monitor_index(
            mons,
            connector=str(state.get("monitor_connector") or ""),
            index=int(state.get("monitor_index") or 0),
        )
        state["monitor_index"] = idx
        mon = mons[idx]
        state["monitor_connector"] = monitor_connector(mon)
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
            favorites, urgent = [], []

        def _fp(block):
            # Timers tick in place — exclude live countdown text from rebuild key.
            return tuple(
                (
                    q.quest_id,
                    q.title,
                    q.deadline_at,
                    q.duration_seconds,
                    tuple((s.title, s.progress) for s in q.steps),
                )
                for q in block
            )

        fingerprint = (
            _fp(favorites),
            _fp(urgent),
            state["interactive"],
            state["collapsed"],
            state["settings_open"],
            state["monitor_index"],
            state["style_pack"],
            state["passthrough_bg_mode"],
            bool(state["toasts_major"]),
            bool(state["toasts_minor"]),
        )
        if not force and fingerprint == state["fingerprint"]:
            return
        state["fingerprint"] = fingerprint
        state["pending_refresh"] = False

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
        mon_opts = [
            (i, monitor_label(m, i, total)) for i, m in enumerate(mons)
        ]
        packs = [(p["id"], p["label"]) for p in list_packs()]

        child, _hotspot, timers = build_hud(
            favorites,
            urgent,
            interactive=state["interactive"],
            collapsed=state["collapsed"],
            settings_open=bool(state["settings_open"]),
            monitors=mon_opts,
            monitor_index=idx,
            style_pack_id=str(state["style_pack"]),
            style_packs=packs,
            passthrough_bg_mode=str(state["passthrough_bg_mode"]),
            passthrough_bg_alpha=float(state["passthrough_bg_alpha"]),
            toasts_major=bool(state["toasts_major"]),
            toasts_minor=bool(state["toasts_minor"]),
            on_select_monitor=select_monitor if state["interactive"] else None,
            on_select_style=set_style_pack if state["interactive"] else None,
            on_passthrough_settings=set_passthrough_settings
            if state["interactive"]
            else None,
            on_toast_settings=set_toast_settings if state["interactive"] else None,
            on_toggle_collapsed=toggle_collapsed,
            on_toggle_settings=toggle_settings if state["interactive"] else None,
            on_prepare_drag_handle=prepare_drag if state["interactive"] else None,
            on_open_quest=open_quest,
        )
        state["timer_bindings"] = timers

        if state["interactive"]:
            hud.add_css_class("hud-window--interactive")
            hud.remove_css_class("hud-window--passthrough")
        else:
            hud.remove_css_class("hud-window--interactive")
            hud.add_css_class("hud-window--passthrough")
        if state["collapsed"]:
            hud.add_css_class("hud-window--collapsed")
            hud.set_opacity(0.1)
        else:
            hud.remove_css_class("hud-window--collapsed")
            hud.set_opacity(1.0)
        hud.set_child(child)
        apply_stored_margins()
        schedule_input_sync()

    def set_collapsed(collapsed: bool) -> str:
        state["collapsed"] = bool(collapsed)
        if state["collapsed"]:
            state["interactive"] = False
            state["settings_open"] = False
        refresh_hud(force=True)
        return "collapsed" if state["collapsed"] else "expanded"

    def toggle_collapsed() -> str:
        if state["collapsed"]:
            return set_collapsed(False)
        return set_collapsed(True)

    def toggle_settings() -> str:
        state["settings_open"] = not bool(state.get("settings_open"))
        refresh_hud(force=True)
        return "settings" if state["settings_open"] else "quests"

    def set_interactive(enabled: bool) -> str:
        state["interactive"] = bool(enabled)
        if state["interactive"]:
            state["collapsed"] = False
        else:
            state["settings_open"] = False
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
        # Explicit cycle: ignore connector preference for this step.
        state["monitor_connector"] = ""
        state["monitor_index"] = cycle_index(state["monitor_index"], len(mons))
        result = sync_monitor()
        apply_stored_margins()
        persist()
        refresh_hud(force=True)
        return result

    def select_monitor(index: int) -> str:
        mons = list_monitors(display)
        if not mons:
            return "no monitors"
        state["monitor_connector"] = ""
        state["monitor_index"] = int(index) % len(mons)
        result = sync_monitor()
        apply_stored_margins()
        persist()
        refresh_hud(force=True)
        return result

    def set_style_pack(name: str) -> str:
        pack = apply_style_pack(name, reload=True)
        state["style_pack"] = pack
        reload_css()
        persist()
        refresh_hud(force=True)
        return f"style: {pack}"

    def set_passthrough_settings(mode: str, alpha: float) -> None:
        mode_key = "full" if str(mode).strip().lower() in {"full", "panel", "solid"} else "chips"
        try:
            a = max(0.0, min(1.0, float(alpha)))
        except (TypeError, ValueError):
            try:
                a = max(0.0, min(1.0, float(state.get("passthrough_bg_alpha", 0.6))))
            except (TypeError, ValueError):
                a = 0.6
        prev_mode = str(state.get("passthrough_bg_mode") or "")
        state["passthrough_bg_mode"] = mode_key
        state["passthrough_bg_alpha"] = a
        apply_passthrough_look()
        persist()
        # Rebuild so mode chips update; skip on alpha-only (scale must stay mounted).
        if mode_key != prev_mode:
            refresh_hud(force=True)

    def set_toast_settings(major: bool, minor: bool) -> None:
        state["toasts_major"] = bool(major)
        state["toasts_minor"] = bool(minor)
        notices.set_enabled(major=state["toasts_major"], minor=state["toasts_minor"])
        persist()
        refresh_hud(force=True)

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
        if c.startswith("style"):
            parts = c.split(maxsplit=1)
            if len(parts) == 1 or parts[1] in {"", "list", "status"}:
                packs = ", ".join(p["id"] for p in list_packs())
                return f"style: {state['style_pack']} [{packs}]"
            return set_style_pack(parts[1].strip())
        if c in {"status", ""}:
            mons = list_monitors(display)
            total = len(mons)
            idx = state["monitor_index"] % total if total else 0
            mon = mons[idx] if total else None
            mode = "interactive" if state["interactive"] else "passthrough"
            fold = "collapsed" if state["collapsed"] else "expanded"
            return (
                f"{mode}; {fold}; style={state['style_pack']}; "
                f"{monitor_label(mon, idx, total)} ({idx + 1}/{total})"
            )
        return f"error: unknown command '{cmd}'"

    def handle_events(events: list[dict]) -> None:
        if not events:
            return
        refresh_hud(force=True)
        for ev in events:
            notices.enqueue(ev)

    def tick_timers() -> bool:
        if apply_timer_bindings(state.get("timer_bindings") or []):
            refresh_hud(force=True)
        elif state.get("pending_refresh"):
            refresh_hud(force=True)
        state["sync_ticks"] = int(state.get("sync_ticks") or 0) + 1
        # Soft data sync ~every DATA_SYNC_MS without waiting for events.
        every = max(1, DATA_SYNC_MS // TIMER_TICK_MS)
        if state["sync_ticks"] % every == 0:
            refresh_hud(force=False)
        return True

    def poll_events() -> bool:
        try:
            revision, events = fetch_events(state["revision"])
        except (urllib.error.URLError, TimeoutError, ValueError, TypeError, KeyError):
            return True

        if revision != state["revision"]:
            new_events = [e for e in events if int(e.get("revision", 0)) > state["revision"]]
            state["revision"] = revision
            if new_events:
                handle_events(new_events)
            else:
                refresh_hud(force=True)
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
    apply_passthrough_look()
    notices.set_enabled(
        major=bool(state["toasts_major"]),
        minor=bool(state["toasts_minor"]),
    )
    refresh_hud(force=True)
    try:
        revision, _ = fetch_events(0)
        state["revision"] = revision
    except (urllib.error.URLError, TimeoutError, ValueError, TypeError, KeyError):
        pass

    ipc_sock = start_server(ipc_handler)

    def on_shutdown(_app) -> None:
        persist()
        stop_server(ipc_sock)

    app.connect("shutdown", on_shutdown)

    GLib.timeout_add(TIMER_TICK_MS, tick_timers)
    GLib.timeout_add(EVENT_POLL_MS, poll_events)
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
