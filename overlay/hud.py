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
    if quest.get("deadline_at"):
        rem = remaining_seconds(quest.get("deadline_at"))  # type: ignore[arg-type]
    if rem is not None and int(rem) <= 0:
        rem = None
    tone = None
    timer_label = None
    if rem is not None:
        tone = timer_tone(quest.get("deadline_at"), quest.get("duration_seconds"))  # type: ignore[arg-type]
        timer_label = format_remaining(int(rem))
    return HudQuest(
        quest_id=int(qid) if qid is not None else None,
        title=quest.get("title") or "?",
        steps=steps,
        timer_label=timer_label,
        timer_tone=tone,
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


def _append_quest_section(
    root: Gtk.Box,
    quest: HudQuest,
    *,
    interactive: bool,
    on_open_quest: Callable[[int], None] | None,
) -> None:
    section = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
    section.add_css_class("hud-section")
    section.set_halign(Gtk.Align.END)

    title_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
    title_row.set_halign(Gtk.Align.END)

    if quest.timer_label:
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
        row.set_halign(Gtk.Align.END)
        row.append(_chip(step.progress, "quest-progress"))
        row.append(_chip(step.title, "quest-title"))
        section.append(row)

    root.append(section)


def build_hud(
    favorites: list[HudQuest],
    urgent: list[HudQuest] | None = None,
    *,
    interactive: bool = False,
    collapsed: bool = False,
    monitor_label: str = "—",
    on_cycle_monitor: Callable[[], None] | None = None,
    on_toggle_collapsed: Callable[[], None] | None = None,
    on_prepare_drag_handle: Callable[[Gtk.Widget], None] | None = None,
    on_open_quest: Callable[[int], None] | None = None,
) -> tuple[Gtk.Widget, Gtk.Widget | None]:
    urgent = urgent or []
    root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
    root.add_css_class("hud")
    if interactive:
        root.add_css_class("hud--interactive")
    if collapsed:
        root.add_css_class("hud--collapsed")
    root.set_halign(Gtk.Align.END)

    header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
    header.add_css_class("hud-header")
    header.set_halign(Gtk.Align.END)

    hotspot: Gtk.Widget | None = None

    if collapsed:
        header.append(_chip("Задачи", "title"))
        root.append(header)
        return root, None

    if interactive and on_cycle_monitor is not None:
        mon_btn = Gtk.Button(label=monitor_label)
        mon_btn.add_css_class("hud-btn")
        mon_btn.add_css_class("hud-chip")
        mon_btn.set_tooltip_text("Сменить монитор")
        mon_btn.set_valign(Gtk.Align.CENTER)
        mon_btn.set_halign(Gtk.Align.END)
        mon_btn.connect("clicked", lambda _b: on_cycle_monitor())
        header.append(mon_btn)
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
        empty = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        empty.add_css_class("hud-section")
        empty.set_halign(Gtk.Align.END)
        empty.append(_chip("Нет активных шагов", "hint"))
        root.append(empty)
    else:
        for quest in favorites:
            _append_quest_section(
                root, quest, interactive=interactive, on_open_quest=on_open_quest
            )

        if favorites and urgent:
            sep = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
            sep.set_halign(Gtk.Align.END)
            sep.append(_rule(heavy=True))
            root.append(sep)

        for quest in urgent:
            _append_quest_section(
                root, quest, interactive=interactive, on_open_quest=on_open_quest
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
        return overlay, hotspot

    return root, hotspot
