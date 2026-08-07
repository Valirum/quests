"""Major (center) + minor (bottom-right) notice hosts."""

from __future__ import annotations

import math
from collections import deque

import cairo
from gi.repository import Gdk, GLib, Gtk, Gtk4LayerShell as LayerShell, Pango

from .idle_notify import get_idle_monitor
from .monitors import apply_monitor, list_monitors
from .sounds import sounds
from .stylepacks import _load_pack, active_pack


def _toast_wrap_width(window: Gtk.Window) -> int:
    """Max content width for major toasts (~2/3 of the output, never past edges)."""
    mon = LayerShell.get_monitor(window)
    if mon is None:
        mons = list_monitors()
        mon = mons[0] if mons else None
    if mon is None:
        return 960
    screen_w = max(1, int(mon.get_geometry().width))
    # Leave side margins so the card never touches the bezel.
    return max(420, min((screen_w * 2) // 3, screen_w - 64))


def _cap_wrap_label(lbl: Gtk.Label, width_px: int) -> None:
    """Force wrap at ``width_px`` and keep natural width from exploding the layout."""
    lbl.set_wrap(True)
    lbl.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
    lbl.set_size_request(width_px, -1)
    lbl.set_hexpand(False)
    lbl.set_halign(Gtk.Align.CENTER)
    # GTK4: NONE keeps natural width = unwrapped line (card blows past the screen).
    # WORD computes natural size with wrapping at the requested width.
    if hasattr(lbl, "set_natural_wrap_mode"):
        try:
            lbl.set_natural_wrap_mode(Gtk.NaturalWrapMode.WORD)
        except Exception:
            pass
    # Character cap as a second brake (avg glyph ≈ width/14; coarse).
    avg = max(8, width_px // 14)
    try:
        lbl.set_max_width_chars(avg)
    except Exception:
        pass

MAJOR_KINDS = frozenset(
    {
        "quest_created",
        "quest_appeared",
        "quest_started",
        "quest_completed",
        "quest_failed",
        "quest_delayed",
    }
)

# After this long on-screen while still waiting for activity, pulse the border.
AFK_BORDER_ALERT_MS = 30_000
# Full sine period for AFK glow (ms); tick interval for smooth updates.
AFK_BORDER_PULSE_PERIOD_MS = 2400
AFK_BORDER_TICK_MS = 33

_DEFAULT_AFK_SIG_RGB = {
    "common": (168, 168, 168),
    "uncommon": (142, 192, 124),
    "epic": (211, 134, 155),
    "legendary": (254, 128, 25),
}

SIGNIFICANCE_LABEL_RU = {
    "common": "обычное",
    "uncommon": "необычное",
    "epic": "эпическое",
    "legendary": "легендарное",
}


def _significance_key(event: dict) -> str:
    raw = event.get("significance") or "common"
    key = str(raw).strip().lower()
    return key if key in SIGNIFICANCE_LABEL_RU else "common"


def _afk_sig_style(sig: str) -> tuple[tuple[int, int, int], int, int, int]:
    """RGB + border radius/width/left-width from the active style pack."""
    mod = _load_pack(active_pack())
    colors = getattr(mod, "AFK_SIG_RGB", None) or _DEFAULT_AFK_SIG_RGB
    rgb = colors.get(sig) or colors.get("common") or _DEFAULT_AFK_SIG_RGB["common"]
    radius = int(
        getattr(mod, "AFK_BORDER_RADIUS", getattr(mod, "PASSTHROUGH_RADIUS", 8))
    )
    width = int(getattr(mod, "AFK_BORDER_WIDTH", 2))
    left = int(getattr(mod, "AFK_BORDER_LEFT_WIDTH", width))
    return (int(rgb[0]), int(rgb[1]), int(rgb[2])), radius, width, left


def _afk_glow_css(
    rgb: tuple[int, int, int],
    *,
    wave: float,
    radius: int,
    width: int,
    left: int,
) -> str:
    """Build CSS for one sine frame. wave is 0..1 (dim → bright)."""
    r, g, b = rgb
    # Floor so the glow never fully dies; peak is intentionally strong.
    w = max(0.0, min(1.0, wave))
    border_a = 0.40 + 0.60 * w
    near_a = 0.35 + 0.65 * w
    mid_a = 0.22 + 0.58 * w
    far_a = 0.10 + 0.45 * w
    inset_a = 0.10 + 0.28 * w
    blur_near = int(22 + 40 * w)
    blur_mid = int(48 + 56 * w)
    blur_far = int(72 + 70 * w)
    inset = int(10 + 18 * w)
    return f"""
.major.major--afk-glow {{
  border-style: solid;
  border-width: {width}px;
  border-left-width: {left}px;
  border-radius: {radius}px;
  border-color: rgba({r}, {g}, {b}, {border_a:.3f});
  box-shadow:
    0 0 {blur_near}px rgba({r}, {g}, {b}, {near_a:.3f}),
    0 0 {blur_mid}px rgba({r}, {g}, {b}, {mid_a:.3f}),
    0 0 {blur_far}px rgba({r}, {g}, {b}, {far_a:.3f}),
    inset 0 0 {inset}px rgba({r}, {g}, {b}, {inset_a:.3f});
}}
"""


def major_eyebrow_parts(kind: str, significance: str) -> tuple[str, str, str]:
    """Prefix, colored significance word, suffix for major eyebrow."""
    word = SIGNIFICANCE_LABEL_RU.get(significance, SIGNIFICANCE_LABEL_RU["common"])
    if kind in {"quest_created", "quest_appeared"}:
        return "Получено ", word, " задание"
    if kind == "quest_started":
        return "Началось ", word, " задание"
    if kind == "quest_completed":
        return "Завершено ", word, " задание"
    if kind == "quest_failed":
        return "Провалено ", word, " задание"
    if kind == "quest_delayed":
        return "Просрочено ", word, " задание"
    return "", MAJOR_EYEBROW.get(kind, kind), ""


MAJOR_EYEBROW = {
    "quest_created": "Получено задание",
    "quest_appeared": "Получено задание",
    "quest_started": "Началось задание",
    "quest_completed": "Задание завершено",
    "quest_failed": "Задание провалено",
    "quest_delayed": "Задание просрочено",
}

MINOR_CHANGE = {
    "step_completed": "Шаг выполнен",
    "status_changed": "Статус изменён",
    "quest_deleted": "Удалено",
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
        sig = _significance_key(event)
        card.add_css_class(f"major--sig-{sig}")
        card.set_halign(Gtk.Align.CENTER)
        card.set_hexpand(False)
        card.set_opacity(0.0)
        wrap_w = _toast_wrap_width(self._window)
        # Card CSS padding is ~48px each side in style packs.
        content_w = max(360, wrap_w - 96)

        width_css = Gtk.CssProvider()
        try:
            width_css.load_from_string(
                f"""
.major {{
  max-width: {wrap_w}px;
}}
.major__title, .major__description, .major__detail {{
  max-width: {content_w}px;
}}
"""
            )
            card.get_style_context().add_provider(
                width_css, Gtk.STYLE_PROVIDER_PRIORITY_USER
            )
        except Exception:
            pass

        def major_label(text: str, css_class: str, *, wrap: bool = False) -> Gtk.Label:
            lbl = Gtk.Label(label=text, xalign=0.5)
            lbl.set_halign(Gtk.Align.CENTER)
            lbl.set_justify(Gtk.Justification.CENTER)
            lbl.add_css_class(css_class)
            if wrap:
                _cap_wrap_label(lbl, content_w)
            return lbl

        prefix, sig_word, suffix = major_eyebrow_parts(kind, sig)
        if prefix or suffix:
            brow = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
            brow.set_halign(Gtk.Align.CENTER)
            brow.set_hexpand(False)
            brow.add_css_class("major__eyebrow-row")
            if prefix:
                brow.append(major_label(prefix, "major__eyebrow"))
            sig_lbl = major_label(sig_word, "major__eyebrow")
            sig_lbl.add_css_class("major__significance")
            sig_lbl.add_css_class(f"major__significance--{sig}")
            brow.append(sig_lbl)
            if suffix:
                brow.append(major_label(suffix, "major__eyebrow"))
            card.append(brow)
        else:
            card.append(major_label(sig_word or kind, "major__eyebrow"))

        card.append(major_label(event.get("title") or "—", "major__title", wrap=True))

        description = (event.get("description") or "").strip()
        if description:
            rule = Gtk.Box()
            rule.add_css_class("major__rule")
            rule.set_halign(Gtk.Align.CENTER)
            rule.set_hexpand(False)
            rule.set_size_request(content_w, 2)
            card.append(rule)
            card.append(major_label(description, "major__description", wrap=True))

        detail = (event.get("detail") or "").strip()
        if detail:
            card.append(major_label(detail, "major__detail", wrap=True))

        self._slot.append(card)
        self._window.present()
        sounds.play(event.get("sound") or kind, source="major")

        done = {"fired": False}
        afk_ui: dict = {"alert": None, "pulse": None, "provider": None, "phase": 0.0}

        def _remove_source(key: str) -> None:
            src = afk_ui[key]
            if src is not None:
                try:
                    GLib.source_remove(src)
                except Exception:
                    pass
                afk_ui[key] = None

        def stop_afk_border() -> None:
            _remove_source("alert")
            _remove_source("pulse")
            card.remove_css_class("major--afk-glow")
            provider = afk_ui.get("provider")
            if provider is not None:
                try:
                    card.get_style_context().remove_provider(provider)
                except Exception:
                    pass
                afk_ui["provider"] = None

        def start_afk_border_pulse() -> None:
            if done["fired"] or afk_ui["pulse"] is not None:
                return
            rgb, radius, width, left = _afk_sig_style(sig)
            provider = Gtk.CssProvider()
            afk_ui["provider"] = provider
            afk_ui["phase"] = 0.0
            card.get_style_context().add_provider(
                provider, Gtk.STYLE_PROVIDER_PRIORITY_USER
            )
            card.add_css_class("major--afk-glow")

            def apply_frame(wave: float) -> None:
                try:
                    provider.load_from_string(
                        _afk_glow_css(
                            rgb,
                            wave=wave,
                            radius=radius,
                            width=width,
                            left=left,
                        )
                    )
                except Exception:
                    pass

            # Start mid-rise so the glow appears immediately.
            apply_frame(0.55)

            period = max(600, AFK_BORDER_PULSE_PERIOD_MS)
            tick_ms = max(16, AFK_BORDER_TICK_MS)
            phase_step = (2.0 * math.pi) * (tick_ms / period)

            def tick() -> bool:
                if done["fired"]:
                    afk_ui["pulse"] = None
                    return False
                afk_ui["phase"] = float(afk_ui["phase"]) + phase_step
                # 0..1 sine; ease keeps a soft floor via _afk_glow_css.
                wave = 0.5 * (1.0 + math.sin(float(afk_ui["phase"])))
                apply_frame(wave)
                return True

            afk_ui["pulse"] = GLib.timeout_add(tick_ms, tick)

        def schedule_afk_border_alert() -> None:
            def fire() -> bool:
                afk_ui["alert"] = None
                if not done["fired"]:
                    start_afk_border_pulse()
                return False

            afk_ui["alert"] = GLib.timeout_add(AFK_BORDER_ALERT_MS, fire)

        def start_fade() -> None:
            if done["fired"]:
                return
            done["fired"] = True
            stop_afk_border()
            get_idle_monitor().cancel_wait()

            def after_out() -> None:
                _clear(self._slot)
                self._busy = False
                if not self._queue:
                    self._window.hide()
                else:
                    self._pump()

            _animate_opacity(card, 1.0, 0.0, fade_out, done=after_out)

        def after_in() -> None:
            def after_hold() -> bool:
                # Stay up while AFK; fade when the user is/becomes active.
                # Fallback: plain hold timer if compositor has no idle-notify.
                if not get_idle_monitor().wait_for_activity(start_fade):
                    start_fade()
                return False

            GLib.timeout_add(hold, after_hold)

        schedule_afk_border_alert()
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
        self.major_enabled = True
        self.minor_enabled = True

    def set_monitor(self, monitor: Gdk.Monitor | None) -> None:
        apply_monitor(self.major._window, monitor)
        apply_monitor(self.minor._window, monitor)

    def set_enabled(self, *, major: bool | None = None, minor: bool | None = None) -> None:
        if major is not None:
            self.major_enabled = bool(major)
        if minor is not None:
            self.minor_enabled = bool(minor)

    def enqueue(self, event: dict) -> None:
        kind = event.get("kind") or ""
        if event.get("toast") is False and kind not in MAJOR_KINDS:
            return
        if kind in MAJOR_KINDS:
            if self.major_enabled:
                self.major.enqueue(event)
            return
        # Quiet kinds stay off-screen unless explicitly toasted.
        if self.minor_enabled and event.get("toast", True):
            self.minor.enqueue(event)
