from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from gi.repository import Gtk

from .deadline import format_remaining, is_urgent, remaining_seconds, timer_tone


@dataclass
class HudStep:
    title: str
    progress: str


@dataclass
class HudQuest:
    quest_id: int | None
    title: str
    steps: list[HudStep]
    timer_label: str | None = None
    timer_tone: str | None = None  # green | orange | red
    deadline_at: object | None = None
    duration_seconds: int | None = None


@dataclass
class TimerBinding:
    """Live countdown chip — update in place without rebuilding the HUD tree."""

    label: Gtk.Label
    deadline_at: object
    duration_seconds: int | None
    tone: str | None = None


def _open_steps(quest: dict) -> list[HudStep]:
    steps: list[HudStep] = []
    for step in quest.get("steps") or []:
        cur = int(step.get("progress_current") or 0)
        total = max(1, int(step.get("progress_total") or 1))
        if step.get("done") or cur >= total:
            continue
        steps.append(HudStep(title=step.get("title") or "?", progress=f"{cur} / {total}"))
    return steps


def _with_timer(quest: dict, steps: list[HudStep]) -> HudQuest:
    qid = quest.get("id")
    rem = None
    deadline = quest.get("deadline_at")
    duration = quest.get("duration_seconds")
    if deadline:
        rem = remaining_seconds(deadline)
    if rem is not None and int(rem) <= 0:
        rem = None
    tone = None
    timer_label = None
    if rem is not None:
        tone = timer_tone(deadline, duration)
        timer_label = format_remaining(int(rem))
    return HudQuest(
        quest_id=int(qid) if qid is not None else None,
        title=quest.get("title") or "?",
        steps=steps,
        timer_label=timer_label,
        timer_tone=tone,
        deadline_at=deadline,
        duration_seconds=int(duration) if duration is not None else None,
    )


def split_hud_quests(items: list[dict]) -> tuple[list[HudQuest], list[HudQuest]]:
    """Pinned (favorites) first; urgent non-pinned below. Pinned wins if both."""
    favorites: list[HudQuest] = []
    urgent: list[HudQuest] = []
    fav_ids: set[int] = set()

    for q in items:
        if q.get("status") in {"completed", "failed", "archived"}:
            continue
        steps = _open_steps(q)
        if not steps:
            continue
        entry = _with_timer(q, steps)
        if q.get("pinned"):
            favorites.append(entry)
            if entry.quest_id is not None:
                fav_ids.add(entry.quest_id)
            continue

    for q in items:
        if q.get("status") in {"completed", "failed", "archived"}:
            continue
        qid = q.get("id")
        if qid is not None and int(qid) in fav_ids:
            continue
        steps = _open_steps(q)
        if not steps:
            continue
        urgent_flag = q.get("urgent")
        if urgent_flag is None:
            urgent_flag = is_urgent(q.get("deadline_at"), q.get("duration_seconds"))
        if not urgent_flag:
            continue
        urgent.append(_with_timer(q, steps))

    return favorites, urgent


MOCK_FAVORITES: list[HudQuest] = [
    HudQuest(
        None,
        "Найти следы у реки",
        [HudStep("Странный отпечаток", "0 / 1")],
        timer_label="1:12:00",
        timer_tone="green",
    ),
]
MOCK_URGENT: list[HudQuest] = [
    HudQuest(
        None,
        "Собрать травы для отвара",
        [HudStep("Луговая трава", "5 / 8")],
        timer_label="0:18:40",
        timer_tone="orange",
    ),
]


def _chip(text: str, css_class: str) -> Gtk.Label:
    lbl = Gtk.Label(label=text)
    lbl.set_halign(Gtk.Align.END)
    lbl.set_xalign(1.0)
    lbl.add_css_class("hud-chip")
    lbl.add_css_class(css_class)
    return lbl


def _rule(*, heavy: bool = False) -> Gtk.Box:
    rule = Gtk.Box()
    rule.add_css_class("section-rule")
    if heavy:
        rule.add_css_class("section-rule--heavy")
    rule.set_halign(Gtk.Align.FILL)
    rule.set_hexpand(True)
    return rule


def apply_timer_bindings(bindings: list[TimerBinding]) -> bool:
    """Update countdown chips in place. True → caller should rebuild HUD (expired)."""
    needs_rebuild = False
    for binding in bindings:
        rem = remaining_seconds(binding.deadline_at)
        if rem is None or rem <= 0:
            needs_rebuild = True
            continue
        text = format_remaining(int(rem))
        tone = timer_tone(binding.deadline_at, binding.duration_seconds) or "red"
        if binding.label.get_label() != text:
            binding.label.set_label(text)
        if binding.tone != tone:
            for old in ("green", "orange", "red"):
                binding.label.remove_css_class(f"quest-timer--{old}")
            binding.label.add_css_class(f"quest-timer--{tone}")
            binding.tone = tone
    return needs_rebuild


def _append_quest_section(
    root: Gtk.Box,
    quest: HudQuest,
    *,
    interactive: bool,
    on_open_quest: Callable[[int], None] | None,
    timers: list[TimerBinding],
) -> None:
    section = Gtk.Box(
        orientation=Gtk.Orientation.VERTICAL,
        spacing=0 if not interactive else 4,
    )
    section.add_css_class("hud-section")
    section.set_halign(Gtk.Align.END)

    title_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
    title_row.add_css_class("hud-row")
    title_row.set_halign(Gtk.Align.END)

    if quest.timer_label and quest.deadline_at is not None:
        tone = quest.timer_tone or "red"
        timer = _chip(quest.timer_label, "quest-timer")
        timer.add_css_class(f"quest-timer--{tone}")
        title_row.append(timer)
        timers.append(
            TimerBinding(
                label=timer,
                deadline_at=quest.deadline_at,
                duration_seconds=quest.duration_seconds,
                tone=tone,
            )
        )
    elif quest.timer_label:
        tone = quest.timer_tone or "red"
        timer = _chip(quest.timer_label, "quest-timer")
        timer.add_css_class(f"quest-timer--{tone}")
        title_row.append(timer)

    if interactive and on_open_quest is not None and quest.quest_id is not None:
        title_btn = Gtk.Button(label=quest.title)
        title_btn.add_css_class("hud-chip")
        title_btn.add_css_class("section-title")
        title_btn.add_css_class("section-title-btn")
        title_btn.set_halign(Gtk.Align.END)
        title_btn.set_tooltip_text("Открыть в задачах")
        title_btn.connect("clicked", lambda _b, qid=quest.quest_id: on_open_quest(qid))
        title_row.append(title_btn)
    else:
        title_row.append(_chip(quest.title, "section-title"))

    section.append(title_row)
    section.append(_rule())

    for step in quest.steps:
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        row.add_css_class("quest")
        row.add_css_class("hud-row")
        row.set_halign(Gtk.Align.END)
        row.append(_chip(step.progress, "quest-progress"))
        row.append(_chip(step.title, "quest-title"))
        section.append(row)

    root.append(section)


def _style_menu_button(
    *,
    style_pack_id: str,
    style_packs: list[tuple[str, str]],
    on_select_style: Callable[[str], None],
) -> Gtk.MenuButton:
    """MenuButton + popover listing available style packs."""
    labels = {pid: label for pid, label in style_packs}
    current = labels.get(style_pack_id, style_pack_id)
    short = (current.split() or [style_pack_id])[0][:10]

    menu_btn = Gtk.MenuButton()
    menu_btn.set_label(short)
    menu_btn.add_css_class("hud-btn")
    menu_btn.add_css_class("hud-chip")
    menu_btn.add_css_class("hud-style")
    menu_btn.set_tooltip_text(f"Стиль: {current}")
    menu_btn.set_valign(Gtk.Align.CENTER)
    menu_btn.set_halign(Gtk.Align.END)
    if hasattr(menu_btn, "set_has_frame"):
        menu_btn.set_has_frame(False)
    try:
        menu_btn.set_direction(Gtk.ArrowType.DOWN)
    except Exception:
        pass

    popover = Gtk.Popover()
    popover.add_css_class("hud-style-popover")
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
    box.add_css_class("hud-style-menu")
    box.set_margin_top(6)
    box.set_margin_bottom(6)
    box.set_margin_start(6)
    box.set_margin_end(6)

    for pack_id, label in style_packs:
        row = Gtk.Button(label=label)
        row.add_css_class("hud-btn")
        row.add_css_class("hud-chip")
        row.add_css_class("hud-style-option")
        if pack_id == style_pack_id:
            row.add_css_class("hud-style-option--active")
        row.set_halign(Gtk.Align.FILL)
        row.set_hexpand(True)

        def _pick(_b: Gtk.Button, pid: str = pack_id) -> None:
            popover.popdown()
            on_select_style(pid)

        row.connect("clicked", _pick)
        box.append(row)

    popover.set_child(box)
    menu_btn.set_popover(popover)
    return menu_btn


def _settings_menu_button(
    *,
    bg_mode: str,
    bg_alpha: float,
    on_change: Callable[[str, float], None],
) -> Gtk.MenuButton:
    """Passthrough look settings (full panel vs chip highlight + alpha)."""
    mode = "full" if str(bg_mode).strip().lower() in {"full", "panel", "solid"} else "chips"
    alpha = max(0.0, min(1.0, float(bg_alpha)))

    menu_btn = Gtk.MenuButton()
    menu_btn.set_label("фон")
    menu_btn.add_css_class("hud-btn")
    menu_btn.add_css_class("hud-chip")
    menu_btn.add_css_class("hud-settings")
    menu_btn.set_tooltip_text("Фон в passthrough: полный / выделение (по строкам) + альфа")
    menu_btn.set_valign(Gtk.Align.CENTER)
    menu_btn.set_halign(Gtk.Align.END)
    if hasattr(menu_btn, "set_has_frame"):
        menu_btn.set_has_frame(False)
    try:
        menu_btn.set_direction(Gtk.ArrowType.DOWN)
    except Exception:
        pass

    popover = Gtk.Popover()
    popover.add_css_class("hud-style-popover")
    popover.add_css_class("hud-settings-popover")
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
    box.add_css_class("hud-style-menu")
    box.add_css_class("hud-settings-menu")
    box.set_margin_top(8)
    box.set_margin_bottom(8)
    box.set_margin_start(10)
    box.set_margin_end(10)

    mode_label = Gtk.Label(label="Фон (passthrough)")
    mode_label.add_css_class("hud-settings-label")
    mode_label.set_halign(Gtk.Align.START)
    box.append(mode_label)

    mode_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
    mode_row.set_halign(Gtk.Align.FILL)
    btn_full = Gtk.ToggleButton(label="полный")
    btn_chips = Gtk.ToggleButton(label="выделение")
    for btn in (btn_full, btn_chips):
        btn.add_css_class("hud-btn")
        btn.add_css_class("hud-chip")
        btn.add_css_class("hud-style-option")
        btn.set_hexpand(True)
        btn.set_halign(Gtk.Align.FILL)
    btn_chips.set_group(btn_full)
    if mode == "full":
        btn_full.set_active(True)
        btn_full.add_css_class("hud-style-option--active")
    else:
        btn_chips.set_active(True)
        btn_chips.add_css_class("hud-style-option--active")
    mode_row.append(btn_full)
    mode_row.append(btn_chips)
    box.append(mode_row)

    alpha_label = Gtk.Label(label="Альфа фона")
    alpha_label.add_css_class("hud-settings-label")
    alpha_label.set_halign(Gtk.Align.START)
    box.append(alpha_label)

    adj = Gtk.Adjustment(
        value=round(alpha * 100),
        lower=0,
        upper=100,
        step_increment=1,
        page_increment=5,
    )
    scale = Gtk.Scale(orientation=Gtk.Orientation.HORIZONTAL, adjustment=adj)
    scale.set_digits(0)
    scale.set_draw_value(True)
    scale.set_value_pos(Gtk.PositionType.RIGHT)
    scale.set_hexpand(True)
    scale.set_size_request(160, -1)
    scale.add_css_class("hud-settings-scale")
    box.append(scale)

    hint = Gtk.Label(label="только вне interactive")
    hint.add_css_class("hint")
    hint.add_css_class("hud-settings-hint")
    hint.set_halign(Gtk.Align.START)
    box.append(hint)

    def _current_mode() -> str:
        return "full" if btn_full.get_active() else "chips"

    def _sync_active_classes() -> None:
        for btn, active in ((btn_full, btn_full.get_active()), (btn_chips, btn_chips.get_active())):
            if active:
                btn.add_css_class("hud-style-option--active")
            else:
                btn.remove_css_class("hud-style-option--active")

    def _emit(*_args) -> None:
        _sync_active_classes()
        on_change(_current_mode(), float(scale.get_value()) / 100.0)

    btn_full.connect("toggled", lambda *_: _emit() if btn_full.get_active() else None)
    btn_chips.connect("toggled", lambda *_: _emit() if btn_chips.get_active() else None)
    scale.connect("value-changed", _emit)

    popover.set_child(box)
    menu_btn.set_popover(popover)
    return menu_btn


def build_hud(
    favorites: list[HudQuest],
    urgent: list[HudQuest] | None = None,
    *,
    interactive: bool = False,
    collapsed: bool = False,
    monitor_label: str = "—",
    style_pack_id: str = "fantasy",
    style_packs: list[tuple[str, str]] | None = None,
    passthrough_bg_mode: str = "chips",
    passthrough_bg_alpha: float = 0.6,
    on_cycle_monitor: Callable[[], None] | None = None,
    on_select_style: Callable[[str], None] | None = None,
    on_passthrough_settings: Callable[[str, float], None] | None = None,
    on_toggle_collapsed: Callable[[], None] | None = None,
    on_prepare_drag_handle: Callable[[Gtk.Widget], None] | None = None,
    on_open_quest: Callable[[int], None] | None = None,
) -> tuple[
    Gtk.Widget,
    Gtk.Widget | None,
    list[TimerBinding],
    Gtk.MenuButton | None,
    Gtk.MenuButton | None,
]:
    urgent = urgent or []
    timers: list[TimerBinding] = []
    style_btn: Gtk.MenuButton | None = None
    settings_btn: Gtk.MenuButton | None = None
    root = Gtk.Box(
        orientation=Gtk.Orientation.VERTICAL,
        spacing=0 if not interactive else 14,
    )
    root.add_css_class("hud")
    if interactive:
        root.add_css_class("hud--interactive")
    if collapsed:
        root.add_css_class("hud--collapsed")
    root.set_halign(Gtk.Align.END)

    header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
    header.add_css_class("hud-header")
    header.add_css_class("hud-row")
    header.set_halign(Gtk.Align.END)

    hotspot: Gtk.Widget | None = None

    if collapsed:
        header.append(_chip("Задачи", "title"))
        root.append(header)
        return root, None, timers, None, None

    if interactive and on_select_style is not None and style_packs:
        style_btn = _style_menu_button(
            style_pack_id=style_pack_id,
            style_packs=style_packs,
            on_select_style=on_select_style,
        )
        header.append(style_btn)
        hotspot = style_btn

    if interactive and on_passthrough_settings is not None:
        settings_btn = _settings_menu_button(
            bg_mode=passthrough_bg_mode,
            bg_alpha=passthrough_bg_alpha,
            on_change=on_passthrough_settings,
        )
        header.append(settings_btn)
        if hotspot is None:
            hotspot = settings_btn

    if interactive and on_cycle_monitor is not None:
        mon_btn = Gtk.Button(label=monitor_label)
        mon_btn.add_css_class("hud-btn")
        mon_btn.add_css_class("hud-chip")
        mon_btn.set_tooltip_text("Сменить монитор")
        mon_btn.set_valign(Gtk.Align.CENTER)
        mon_btn.set_halign(Gtk.Align.END)
        mon_btn.connect("clicked", lambda _b: on_cycle_monitor())
        header.append(mon_btn)
        if hotspot is None:
            hotspot = mon_btn

    if interactive and on_toggle_collapsed is not None:
        fold_btn = Gtk.Button(label="─")
        fold_btn.add_css_class("hud-btn")
        fold_btn.add_css_class("hud-chip")
        fold_btn.add_css_class("hud-fold")
        fold_btn.set_tooltip_text("Свернуть HUD (Backspace)")
        fold_btn.set_valign(Gtk.Align.CENTER)
        fold_btn.set_halign(Gtk.Align.END)
        fold_btn.connect("clicked", lambda _b: on_toggle_collapsed())
        header.append(fold_btn)
        if hotspot is None:
            hotspot = fold_btn

    header.append(_chip("Задачи", "title"))
    root.append(header)

    if not favorites and not urgent:
        empty = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=0 if not interactive else 4,
        )
        empty.add_css_class("hud-section")
        empty.set_halign(Gtk.Align.END)
        hint_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        hint_row.add_css_class("hud-row")
        hint_row.set_halign(Gtk.Align.END)
        hint_row.append(_chip("Нет активных шагов", "hint"))
        empty.append(hint_row)
        root.append(empty)
    else:
        for quest in favorites:
            _append_quest_section(
                root,
                quest,
                interactive=interactive,
                on_open_quest=on_open_quest,
                timers=timers,
            )

        if favorites and urgent:
            sep = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
            sep.set_halign(Gtk.Align.END)
            sep.append(_rule(heavy=True))
            root.append(sep)

        for quest in urgent:
            _append_quest_section(
                root,
                quest,
                interactive=interactive,
                on_open_quest=on_open_quest,
                timers=timers,
            )

    if interactive and on_prepare_drag_handle is not None:
        overlay = Gtk.Overlay()
        overlay.set_child(root)
        drag = Gtk.Button(label="⠿")
        drag.add_css_class("hud-drag")
        drag.set_tooltip_text("Перетащить HUD")
        drag.set_halign(Gtk.Align.START)
        drag.set_valign(Gtk.Align.START)
        drag.set_cursor_from_name("grab")
        drag.set_can_focus(False)
        if hasattr(drag, "set_has_frame"):
            drag.set_has_frame(False)
        on_prepare_drag_handle(drag)
        overlay.add_overlay(drag)
        return overlay, hotspot, timers, style_btn, settings_btn

    return root, hotspot, timers, style_btn, settings_btn
