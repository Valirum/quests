from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from gi.repository import Gtk

from .deadline import format_remaining, is_urgent, remaining_seconds, timer_tone

# Header control glyphs (theme-independent).
ICON_FOLD = "−"
ICON_GEAR = "⚙"
ICON_LIST = "☰"


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
    timer_tone: str | None = None  # green | orange | red | overdue
    deadline_at: object | None = None
    duration_seconds: int | None = None
    overdue: bool = False


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
    status = str(quest.get("status") or "")
    overdue = status == "delayed"
    if deadline:
        rem = remaining_seconds(deadline)
        if rem is not None and int(rem) <= 0:
            overdue = True
            rem = None
    tone = None
    timer_label = None
    if rem is not None:
        tone = timer_tone(deadline, duration)
        timer_label = format_remaining(int(rem))
    elif overdue:
        tone = "overdue"
        timer_label = "просрочено"
    return HudQuest(
        quest_id=int(qid) if qid is not None else None,
        title=quest.get("title") or "?",
        steps=steps,
        timer_label=timer_label,
        timer_tone=tone,
        deadline_at=deadline if rem is not None else None,
        duration_seconds=int(duration) if duration is not None else None,
        overdue=overdue,
    )


def split_hud_quests(
    items: list[dict],
    *,
    category_slug: str | None = None,
) -> tuple[list[HudQuest], list[HudQuest], list[HudQuest]]:
    """Pinned → urgent → category (active/delayed). Earlier lanes win on overlap."""
    favorites: list[HudQuest] = []
    urgent: list[HudQuest] = []
    category: list[HudQuest] = []
    taken: set[int] = set()
    slug = (category_slug or "").strip().lower() or None

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
                taken.add(entry.quest_id)

    for q in items:
        if q.get("status") in {"completed", "failed", "archived"}:
            continue
        qid = q.get("id")
        if qid is not None and int(qid) in taken:
            continue
        steps = _open_steps(q)
        if not steps:
            continue
        urgent_flag = q.get("urgent")
        if urgent_flag is None:
            urgent_flag = is_urgent(q.get("deadline_at"), q.get("duration_seconds"))
        if not urgent_flag:
            continue
        entry = _with_timer(q, steps)
        urgent.append(entry)
        if entry.quest_id is not None:
            taken.add(entry.quest_id)

    if slug:
        for q in items:
            status = str(q.get("status") or "")
            if status not in {"active", "delayed"}:
                continue
            qid = q.get("id")
            if qid is not None and int(qid) in taken:
                continue
            q_slug = str(q.get("category_slug") or "").strip().lower()
            if q_slug != slug:
                continue
            steps = _open_steps(q)
            if not steps:
                continue
            category.append(_with_timer(q, steps))

    return favorites, urgent, category


def resolve_hud_category(
    categories: list[dict],
    preferred: str | None,
) -> tuple[str, str, list[tuple[str, str]]]:
    """Pick slug/label and option list for settings / cycling.

    Returns (slug, label, options[(slug, label)]). Empty categories → ("", "", []).
    """
    options: list[tuple[str, str]] = []
    for cat in categories:
        s = str(cat.get("slug") or "").strip()
        if not s:
            continue
        label = str(cat.get("label") or s).strip() or s
        options.append((s, label))
    if not options:
        return "", "", []
    want = (preferred or "").strip().lower()
    for s, label in options:
        if s.lower() == want:
            return s, label, options
    s0, label0 = options[0]
    return s0, label0, options


def cycle_hud_category(
    categories: list[dict],
    current: str | None,
    *,
    delta: int,
) -> str:
    """Cycle category slug by delta (±1). Returns new slug (or "")."""
    slug, _label, options = resolve_hud_category(categories, current)
    if not options:
        return ""
    slugs = [s for s, _ in options]
    try:
        idx = next(i for i, s in enumerate(slugs) if s.lower() == slug.lower())
    except StopIteration:
        idx = 0
    return slugs[(idx + int(delta)) % len(slugs)]


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
    # Hug CSS min-width; never hexpand — that stretches the layer-shell surface
    # full-output-wide in passthrough and leaves a ghost separator bar.
    rule.set_halign(Gtk.Align.END)
    rule.set_hexpand(False)
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
            for old in ("green", "orange", "red", "overdue"):
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
    title_row.set_hexpand(False)

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
        tone = quest.timer_tone or ("overdue" if quest.overdue else "red")
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
        row.set_hexpand(False)
        row.append(_chip(step.progress, "quest-progress"))
        row.append(_chip(step.title, "quest-title"))
        section.append(row)

    root.append(section)


def _append_section_heading(root: Gtk.Box, text: str, *, interactive: bool) -> None:
    block = Gtk.Box(
        orientation=Gtk.Orientation.VERTICAL,
        spacing=0 if not interactive else 2,
    )
    block.add_css_class("hud-section")
    block.add_css_class("hud-section--lane")
    block.set_halign(Gtk.Align.END)
    row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
    row.add_css_class("hud-row")
    row.set_halign(Gtk.Align.END)
    row.set_hexpand(False)
    row.append(_chip(text, "section-heading"))
    block.append(row)
    root.append(block)


def _append_heavy_sep(root: Gtk.Box) -> None:
    sep = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
    sep.set_halign(Gtk.Align.END)
    sep.append(_rule(heavy=True))
    root.append(sep)


def _icon_button(
    glyph: str,
    *,
    tooltip: str,
    css_extra: str,
    on_click: Callable[[], None],
) -> Gtk.Button:
    btn = Gtk.Button(label=glyph)
    btn.add_css_class("hud-icon-btn")
    btn.add_css_class(css_extra)
    btn.set_tooltip_text(tooltip)
    btn.set_valign(Gtk.Align.CENTER)
    btn.set_halign(Gtk.Align.CENTER)
    btn.set_can_focus(False)
    if hasattr(btn, "set_has_frame"):
        btn.set_has_frame(False)
    btn.connect("clicked", lambda _b: on_click())
    return btn


def _settings_label(text: str) -> Gtk.Label:
    lbl = Gtk.Label(label=text)
    lbl.add_css_class("hud-settings-label")
    lbl.set_halign(Gtk.Align.END)
    lbl.set_xalign(1.0)
    return lbl


def _opt_slider(
    options: list[tuple[str, str]],
    active_id: str,
    on_pick: Callable[[str], None],
) -> Gtk.Box:
    """Horizontal exclusive option chips (monitor / style / bg mode)."""
    row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
    row.add_css_class("hud-opt-slider")
    row.set_halign(Gtk.Align.END)
    row.set_hexpand(True)

    for i, (oid, label) in enumerate(options):
        btn = Gtk.Button(label=label)
        btn.add_css_class("hud-opt")
        if oid == active_id:
            btn.add_css_class("hud-opt--on")
        if i == 0:
            btn.add_css_class("hud-opt--first")
        if i == len(options) - 1:
            btn.add_css_class("hud-opt--last")
        btn.set_hexpand(True)
        btn.set_halign(Gtk.Align.FILL)
        if hasattr(btn, "set_has_frame"):
            btn.set_has_frame(False)

        def _pick(_b: Gtk.Button, picked: str = oid) -> None:
            on_pick(picked)

        btn.connect("clicked", _pick)
        row.append(btn)
    return row


def _append_settings_panel(
    root: Gtk.Box,
    *,
    monitors: list[tuple[int, str]],
    monitor_index: int,
    style_pack_id: str,
    style_packs: list[tuple[str, str]],
    categories: list[tuple[str, str]],
    category_slug: str,
    bg_mode: str,
    bg_alpha: float,
    toasts_major: bool,
    toasts_minor: bool,
    on_select_monitor: Callable[[int], None] | None,
    on_select_style: Callable[[str], None] | None,
    on_select_category: Callable[[str], None] | None,
    on_passthrough_settings: Callable[[str, float], None] | None,
    on_toast_settings: Callable[[bool, bool], None] | None,
) -> None:
    panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
    panel.add_css_class("hud-settings-panel")
    panel.set_halign(Gtk.Align.END)
    panel.set_size_request(260, -1)

    mode = "full" if str(bg_mode).strip().lower() in {"full", "panel", "solid"} else "chips"
    alpha = max(0.0, min(1.0, float(bg_alpha)))
    on_off = [("1", "вкл"), ("0", "выкл")]

    # Monitor
    panel.append(_settings_label("Монитор"))
    if monitors and on_select_monitor is not None:
        mon_opts = [(str(i), label) for i, label in monitors]
        active_mon = str(monitor_index if any(i == monitor_index for i, _ in monitors) else monitors[0][0])

        def _pick_mon(oid: str) -> None:
            on_select_monitor(int(oid))

        panel.append(_opt_slider(mon_opts, active_mon, _pick_mon))
    else:
        panel.append(_chip("нет мониторов", "hint"))

    # Style
    panel.append(_settings_label("Стиль"))
    if style_packs and on_select_style is not None:
        panel.append(_opt_slider(style_packs, style_pack_id, on_select_style))
    else:
        panel.append(_chip(style_pack_id, "hint"))

    # Category lane
    panel.append(_settings_label("Раздел в HUD"))
    if categories and on_select_category is not None:
        active_cat = category_slug if any(s == category_slug for s, _ in categories) else categories[0][0]
        panel.append(_opt_slider(categories, active_cat, on_select_category))
        cat_hint = Gtk.Label(label="z / x — листать раздел")
        cat_hint.add_css_class("hint")
        cat_hint.add_css_class("hud-settings-hint")
        cat_hint.set_halign(Gtk.Align.END)
        cat_hint.set_xalign(1.0)
        panel.append(cat_hint)
    else:
        panel.append(_chip("нет разделов", "hint"))

    # Background mode
    panel.append(_settings_label("Фон (passthrough)"))
    bg_opts = [("chips", "выделение"), ("full", "полный")]

    def _pick_bg(oid: str) -> None:
        if on_passthrough_settings is None:
            return
        on_passthrough_settings(oid, alpha)

    panel.append(_opt_slider(bg_opts, mode, _pick_bg))

    # Alpha
    panel.append(_settings_label("Альфа фона"))
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
    scale.set_size_request(220, -1)
    scale.add_css_class("hud-settings-scale")
    scale.set_halign(Gtk.Align.FILL)

    def _on_alpha(*_args) -> None:
        if on_passthrough_settings is None:
            return
        on_passthrough_settings(mode, float(scale.get_value()) / 100.0)

    scale.connect("value-changed", _on_alpha)
    panel.append(scale)

    hint = Gtk.Label(label="фон виден только вне interactive")
    hint.add_css_class("hint")
    hint.add_css_class("hud-settings-hint")
    hint.set_halign(Gtk.Align.END)
    hint.set_xalign(1.0)
    panel.append(hint)

    # Toasts
    panel.append(_settings_label("Тосты полноэкранные"))
    major_on = bool(toasts_major)
    minor_on = bool(toasts_minor)

    def _pick_major(oid: str) -> None:
        if on_toast_settings is None:
            return
        on_toast_settings(oid == "1", minor_on)

    def _pick_minor(oid: str) -> None:
        if on_toast_settings is None:
            return
        on_toast_settings(major_on, oid == "1")

    panel.append(_opt_slider(on_off, "1" if major_on else "0", _pick_major))
    panel.append(_settings_label("Тосты мелкие"))
    panel.append(_opt_slider(on_off, "1" if minor_on else "0", _pick_minor))

    root.append(panel)


def build_hud(
    favorites: list[HudQuest],
    urgent: list[HudQuest] | None = None,
    category: list[HudQuest] | None = None,
    *,
    interactive: bool = False,
    collapsed: bool = False,
    settings_open: bool = False,
    monitors: list[tuple[int, str]] | None = None,
    monitor_index: int = 0,
    style_pack_id: str = "fantasy",
    style_packs: list[tuple[str, str]] | None = None,
    categories: list[tuple[str, str]] | None = None,
    category_slug: str = "",
    category_label: str = "",
    passthrough_bg_mode: str = "chips",
    passthrough_bg_alpha: float = 0.6,
    toasts_major: bool = True,
    toasts_minor: bool = True,
    on_select_monitor: Callable[[int], None] | None = None,
    on_select_style: Callable[[str], None] | None = None,
    on_select_category: Callable[[str], None] | None = None,
    on_passthrough_settings: Callable[[str, float], None] | None = None,
    on_toast_settings: Callable[[bool, bool], None] | None = None,
    on_toggle_collapsed: Callable[[], None] | None = None,
    on_toggle_settings: Callable[[], None] | None = None,
    on_prepare_drag_handle: Callable[[Gtk.Widget], None] | None = None,
    on_open_quest: Callable[[int], None] | None = None,
) -> tuple[Gtk.Widget, Gtk.Widget | None, list[TimerBinding]]:
    urgent = urgent or []
    category = category or []
    monitors = monitors or []
    style_packs = style_packs or []
    categories = categories or []
    timers: list[TimerBinding] = []
    show_settings = bool(interactive and settings_open and not collapsed)

    root = Gtk.Box(
        orientation=Gtk.Orientation.VERTICAL,
        spacing=0 if not interactive else 14,
    )
    root.add_css_class("hud")
    if interactive:
        root.add_css_class("hud--interactive")
    if collapsed:
        root.add_css_class("hud--collapsed")
    if show_settings:
        root.add_css_class("hud--settings")
    root.set_halign(Gtk.Align.END)

    header = Gtk.Box(
        orientation=Gtk.Orientation.VERTICAL,
        spacing=0,
    )
    header.add_css_class("hud-header")
    header.set_halign(Gtk.Align.END)

    hotspot: Gtk.Widget | None = None
    controls: Gtk.Widget | None = None

    if collapsed:
        title_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        title_row.add_css_class("hud-row")
        title_row.set_halign(Gtk.Align.END)
        title_row.set_hexpand(False)
        title_row.append(_chip("Задачи", "title"))
        header.append(title_row)
        root.append(header)
        return root, None, timers

    # Fold/gear sit as overlays at the window corner (like drag) — built after root.
    if interactive and (on_toggle_collapsed is not None or on_toggle_settings is not None):
        controls = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=2)
        controls.add_css_class("hud-header-controls")
        controls.set_halign(Gtk.Align.END)
        controls.set_valign(Gtk.Align.START)

        if on_toggle_collapsed is not None:
            fold_btn = _icon_button(
                ICON_FOLD,
                tooltip="Свернуть HUD (Backspace)",
                css_extra="hud-icon-btn--fold",
                on_click=on_toggle_collapsed,
            )
            controls.append(fold_btn)
            hotspot = fold_btn

        if on_toggle_settings is not None:
            gear_btn = _icon_button(
                ICON_LIST if show_settings else ICON_GEAR,
                tooltip="К квестам" if show_settings else "Настройки",
                css_extra="hud-icon-btn--gear",
                on_click=on_toggle_settings,
            )
            controls.append(gear_btn)
            hotspot = gear_btn

    title_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
    title_row.add_css_class("hud-row")
    title_row.set_halign(Gtk.Align.END)
    title_row.set_hexpand(False)
    title_row.append(_chip("Настройки" if show_settings else "Задачи", "title"))
    # Reserve vertical room: fold/gear are overlaid flush to the corner above the title.
    if controls is not None:
        spacer = Gtk.Box()
        spacer.set_size_request(-1, 22)
        header.append(spacer)
    header.append(title_row)

    root.append(header)

    if show_settings:
        _append_settings_panel(
            root,
            monitors=monitors,
            monitor_index=monitor_index,
            style_pack_id=style_pack_id,
            style_packs=style_packs,
            categories=categories,
            category_slug=category_slug,
            bg_mode=passthrough_bg_mode,
            bg_alpha=passthrough_bg_alpha,
            toasts_major=toasts_major,
            toasts_minor=toasts_minor,
            on_select_monitor=on_select_monitor,
            on_select_style=on_select_style,
            on_select_category=on_select_category,
            on_passthrough_settings=on_passthrough_settings,
            on_toast_settings=on_toast_settings,
        )
    elif not favorites and not urgent and not category:
        empty = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=0 if not interactive else 4,
        )
        empty.add_css_class("hud-section")
        empty.set_halign(Gtk.Align.END)
        hint_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        hint_row.add_css_class("hud-row")
        hint_row.set_halign(Gtk.Align.END)
        hint_row.set_hexpand(False)
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
            _append_heavy_sep(root)

        for quest in urgent:
            _append_quest_section(
                root,
                quest,
                interactive=interactive,
                on_open_quest=on_open_quest,
                timers=timers,
            )

        # Category lane only when it has something to show (avoid orphan heading
        # + empty hint that still paints a stray passthrough bar).
        if category:
            if favorites or urgent:
                _append_heavy_sep(root)
            heading = (category_label or category_slug or "Раздел").strip()
            _append_section_heading(root, heading, interactive=interactive)
            for quest in category:
                _append_quest_section(
                    root,
                    quest,
                    interactive=interactive,
                    on_open_quest=on_open_quest,
                    timers=timers,
                )

    if interactive and (
        on_prepare_drag_handle is not None or controls is not None
    ):
        overlay = Gtk.Overlay()
        overlay.set_child(root)

        # Fold/gear: flush to top-right window corner (outside content padding).
        if controls is not None:
            overlay.add_overlay(controls)

        if on_prepare_drag_handle is not None:
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

        return overlay, hotspot, timers

    return root, hotspot, timers
