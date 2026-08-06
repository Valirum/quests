"""Persistent chat registry + notification dedup."""

from __future__ import annotations

import json
import threading
from pathlib import Path


class JsonStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._lock = threading.Lock()

    def _read(self) -> dict:
        if not self.path.is_file():
            return {}
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}

    def _write(self, data: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        tmp.replace(self.path)


class ChatRegistry(JsonStore):
    """Map allowed user_id → private chat_id (usually the same)."""

    def remember(self, user_id: int, chat_id: int) -> None:
        with self._lock:
            data = self._read()
            chats = dict(data.get("chats") or {})
            chats[str(user_id)] = int(chat_id)
            data["chats"] = chats
            self._write(data)

    def chat_ids(self, allowed: frozenset[int]) -> list[int]:
        with self._lock:
            data = self._read()
            chats = data.get("chats") or {}
            out: list[int] = []
            for uid in allowed:
                raw = chats.get(str(uid))
                if raw is not None:
                    out.append(int(raw))
                else:
                    # Private chats: chat_id == user_id until /start stored.
                    out.append(int(uid))
            return sorted(set(out))


class NotifyDedup(JsonStore):
    """Remember sent (quest_id, kind) keys + last TG message ids per quest."""

    def __init__(self, path: str | Path, *, maxlen: int = 2000) -> None:
        super().__init__(path)
        self.maxlen = maxlen

    @staticmethod
    def key(quest_id: int | None, kind: str) -> str:
        q = int(quest_id) if quest_id is not None else 0
        return f"{q}:{kind}"

    def already(self, quest_id: int | None, kind: str) -> bool:
        with self._lock:
            keys = list(self._read().get("keys") or [])
            return self.key(quest_id, kind) in keys

    def mark(self, quest_id: int | None, kind: str) -> bool:
        """Return True if newly marked (should send), False if duplicate."""
        with self._lock:
            data = self._read()
            keys: list[str] = list(data.get("keys") or [])
            k = self.key(quest_id, kind)
            if k in keys:
                return False
            keys.append(k)
            if len(keys) > self.maxlen:
                keys = keys[-self.maxlen :]
            data["keys"] = keys
            self._write(data)
            return True

    def list_quest_messages(self, quest_id: int) -> list[tuple[int, int]]:
        """Return tracked (chat_id, message_id) without removing them."""
        with self._lock:
            raw = list((self._read().get("quest_msgs") or {}).get(str(int(quest_id))) or [])
        out: list[tuple[int, int]] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            try:
                out.append((int(item["chat_id"]), int(item["message_id"])))
            except (KeyError, TypeError, ValueError):
                continue
        return out

    def take_quest_messages(self, quest_id: int) -> list[tuple[int, int]]:
        """Pop tracked (chat_id, message_id) for quest; empty if none."""
        with self._lock:
            data = self._read()
            msgs = dict(data.get("quest_msgs") or {})
            raw = list(msgs.pop(str(int(quest_id)), []) or [])
            data["quest_msgs"] = msgs
            self._write(data)
        out: list[tuple[int, int]] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            try:
                out.append((int(item["chat_id"]), int(item["message_id"])))
            except (KeyError, TypeError, ValueError):
                continue
        return out

    def set_quest_messages(
        self, quest_id: int, items: list[tuple[int, int]]
    ) -> None:
        """Replace tracked messages for a quest (empty clears)."""
        with self._lock:
            data = self._read()
            msgs = dict(data.get("quest_msgs") or {})
            qk = str(int(quest_id))
            if not items:
                msgs.pop(qk, None)
            else:
                msgs[qk] = [
                    {"chat_id": int(c), "message_id": int(m)} for c, m in items
                ]
            data["quest_msgs"] = msgs
            self._write(data)

    def remember_quest_message(
        self, quest_id: int, chat_id: int, message_id: int
    ) -> None:
        with self._lock:
            data = self._read()
            msgs = dict(data.get("quest_msgs") or {})
            qk = str(int(quest_id))
            bucket: list = list(msgs.get(qk) or [])
            bucket.append(
                {"chat_id": int(chat_id), "message_id": int(message_id)}
            )
            # Cap per-quest history (shouldn't grow if we take+replace).
            if len(bucket) > 40:
                bucket = bucket[-40:]
            msgs[qk] = bucket
            # Bound total tracked quests.
            if len(msgs) > self.maxlen:
                # Drop oldest keys by insertion order (Py3.7+).
                overflow = len(msgs) - self.maxlen
                for drop_k in list(msgs.keys())[:overflow]:
                    msgs.pop(drop_k, None)
            data["quest_msgs"] = msgs
            self._write(data)
