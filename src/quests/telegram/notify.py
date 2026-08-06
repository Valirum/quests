"""Push notifications from Quests events + deadline window starts."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any

from aiogram import Bot
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest

from quests.telegram.api_client import ApiError, QuestsApi
from quests.telegram.formatters import format_quest_card, status_label
from quests.telegram.keyboards import quest_keyboard
from quests.telegram.resilience import tg_retry
from quests.telegram.settings import TgSettings
from quests.telegram.store import ChatRegistry, NotifyDedup
from quests.timeutil import ensure_utc, is_in_urgent_window

log = logging.getLogger("quests.telegram.notify")

# Domain kinds → TG push.
NOTIFY_KINDS = {
    "quest_completed": "Выполнено",
    "quest_failed": "Провал",
    "quest_delayed": "Просрочено",
    # периодические инстансы (ручной create через /new уже отвечает в чат)
    "quest_appeared": "Новая задача",
}

POLL_EVENTS_S = 3.0
POLL_WINDOWS_S = 15.0


def _html_escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


async def _try_delete_message(bot: Bot, chat_id: int, message_id: int) -> bool:
    """True if gone (deleted or already absent). False if network gave up."""
    try:
        await tg_retry(
            lambda: bot.delete_message(chat_id, message_id),
            label=f"notify-del:{chat_id}:{message_id}",
        )
        return True
    except TelegramBadRequest:
        return True
    except Exception as e:
        log.warning("notify delete failed chat=%s mid=%s: %s", chat_id, message_id, e)
        return False


async def _replace_quest_notice(
    bot: Bot,
    dedup: NotifyDedup,
    settings: TgSettings,
    chats: ChatRegistry,
    text: str,
    *,
    reply_markup=None,
    quest_id: int,
) -> None:
    """Edit existing notice in place; else delete old + send new.

    Failed deletes stay tracked so a later update can still wipe them.
    """
    old = dedup.list_quest_messages(quest_id)
    by_chat: dict[int, list[int]] = {}
    for chat_id, message_id in old:
        by_chat.setdefault(int(chat_id), []).append(int(message_id))

    kept: list[tuple[int, int]] = []
    target_chats = chats.chat_ids(settings.user_ids)

    for chat_id in target_chats:
        mids = list(by_chat.pop(chat_id, []))
        edited = False
        if mids:
            # Prefer editing the newest tracked message for this chat.
            edit_mid = mids[-1]
            extras = mids[:-1]
            try:
                await tg_retry(
                    lambda c=chat_id, m=edit_mid: bot.edit_message_text(
                        text,
                        chat_id=c,
                        message_id=m,
                        parse_mode=ParseMode.HTML,
                        reply_markup=reply_markup,
                    ),
                    label=f"notify-edit:{chat_id}:{edit_mid}",
                )
                kept.append((chat_id, edit_mid))
                edited = True
            except TelegramBadRequest as e:
                err = str(e).lower()
                if "message is not modified" in err:
                    kept.append((chat_id, edit_mid))
                    edited = True
                else:
                    extras = mids  # edit failed → delete all including this
            except Exception:
                log.warning(
                    "notify edit failed chat=%s mid=%s; will resend",
                    chat_id,
                    edit_mid,
                    exc_info=True,
                )
                extras = mids

            for mid in extras:
                if not await _try_delete_message(bot, chat_id, mid):
                    kept.append((chat_id, mid))

        if edited:
            continue

        try:
            msg = await tg_retry(
                lambda c=chat_id: bot.send_message(
                    c,
                    text,
                    parse_mode=ParseMode.HTML,
                    reply_markup=reply_markup,
                ),
                label=f"notify-send:{chat_id}",
            )
            if msg.message_id:
                kept.append((chat_id, int(msg.message_id)))
        except Exception:
            log.exception("notify send failed chat_id=%s", chat_id)

    # Orphan chats no longer in whitelist — still try to delete.
    for chat_id, mids in by_chat.items():
        for mid in mids:
            if not await _try_delete_message(bot, chat_id, mid):
                kept.append((chat_id, mid))

    dedup.set_quest_messages(quest_id, kept)


async def _send_all(
    bot: Bot,
    chats: ChatRegistry,
    settings: TgSettings,
    text: str,
    *,
    reply_markup=None,
    dedup: NotifyDedup | None = None,
    quest_id: int | None = None,
) -> None:
    if quest_id is not None and dedup is not None:
        await _replace_quest_notice(
            bot,
            dedup,
            settings,
            chats,
            text,
            reply_markup=reply_markup,
            quest_id=int(quest_id),
        )
        return

    for chat_id in chats.chat_ids(settings.user_ids):
        try:
            await tg_retry(
                lambda c=chat_id: bot.send_message(
                    c,
                    text,
                    parse_mode=ParseMode.HTML,
                    reply_markup=reply_markup,
                ),
                label=f"notify-send:{chat_id}",
            )
        except Exception:
            log.exception("notify send failed chat_id=%s", chat_id)


async def _handle_event(
    bot: Bot,
    api: QuestsApi,
    chats: ChatRegistry,
    dedup: NotifyDedup,
    settings: TgSettings,
    ev: dict[str, Any],
) -> None:
    kind = str(ev.get("kind") or "")
    if kind not in NOTIFY_KINDS:
        return
    quest_id = ev.get("quest_id")
    if quest_id is not None:
        quest_id = int(quest_id)
    if not dedup.mark(quest_id, kind):
        return

    headline = NOTIFY_KINDS[kind]
    title = _html_escape(str(ev.get("title") or ""))
    detail = _html_escape(str(ev.get("detail") or ""))
    lines = [f"<b>{headline}</b>", title]
    if detail:
        lines.append(detail)

    markup = None
    if quest_id:
        try:
            q = await api.get_quest(quest_id)
            lines = [
                f"<b>{headline}</b>",
                format_quest_card(q),
            ]
            markup = quest_keyboard(q)
        except ApiError:
            pass

    await _send_all(
        bot,
        chats,
        settings,
        "\n".join(lines),
        reply_markup=markup,
        dedup=dedup,
        quest_id=quest_id,
    )


async def events_loop(
    bot: Bot,
    api: QuestsApi,
    chats: ChatRegistry,
    dedup: NotifyDedup,
    settings: TgSettings,
) -> None:
    since = 0
    try:
        since = await api.sync_revision()
    except ApiError:
        log.warning("API sync unavailable at notify start; will retry")

    while True:
        try:
            payload = await api.events_since(since)
            events = list(payload.get("events") or [])
            since = int(payload.get("revision") or since)
            try:
                await api.heartbeat(component="telegram")
            except ApiError:
                pass
            for ev in events:
                if not isinstance(ev, dict):
                    continue
                await _handle_event(bot, api, chats, dedup, settings, ev)
        except ApiError as e:
            log.warning("events poll: %s", e)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("events poll failed")
        await asyncio.sleep(POLL_EVENTS_S)


def _deadline_dt(raw: object) -> datetime | None:
    if not raw:
        return None
    try:
        return ensure_utc(datetime.fromisoformat(str(raw)))
    except ValueError:
        return None


async def _active_in_window(api: QuestsApi) -> list[dict]:
    quests = await api.list_quests(status="active")
    now = datetime.now().astimezone()
    out: list[dict] = []
    for q in quests:
        duration = q.get("duration_seconds")
        dl = _deadline_dt(q.get("deadline_at"))
        if dl is None or not duration:
            continue
        if is_in_urgent_window(dl, int(duration), now=now):
            out.append(q)
    return out


async def window_start_loop(
    bot: Bot,
    api: QuestsApi,
    chats: ChatRegistry,
    dedup: NotifyDedup,
    settings: TgSettings,
) -> None:
    """Notify when (deadline − duration) has passed for an active quest."""
    # Не спамить уже открытыми окнами при старте бота — только новые пересечения.
    try:
        for q in await _active_in_window(api):
            dedup.mark(int(q["id"]), "quest_started")
    except ApiError as e:
        log.warning("window seed: %s", e)

    while True:
        try:
            for q in await _active_in_window(api):
                qid = int(q["id"])
                if not dedup.mark(qid, "quest_started"):
                    continue
                text = (
                    "<b>Задача началась</b>\n"
                    f"Окно срока открыто · статус: {status_label(q.get('status'))}\n\n"
                    f"{format_quest_card(q)}"
                )
                await _send_all(
                    bot,
                    chats,
                    settings,
                    text,
                    reply_markup=quest_keyboard(q),
                    dedup=dedup,
                    quest_id=qid,
                )
        except ApiError as e:
            log.warning("window poll: %s", e)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("window poll failed")
        await asyncio.sleep(POLL_WINDOWS_S)
