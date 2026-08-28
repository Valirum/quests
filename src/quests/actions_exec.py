"""Execute (or dry-run preview) an ActionBatch against the Quests HTTP API.

Non-agentic counterpart to the quests-MCP tools: the whole batch is produced
once by the LLM (``quests.llm.extract_action_batch_sync``), validated, then
applied deterministically here — same HTTP endpoints ``mcp_server.py`` calls,
same name/substring resolution (``quests.refs``). ``dry_run=True`` builds a
before/after preview without writing, using negative placeholder ids for
entities that don't exist yet (``create_questline``/``create_quest``).
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

from quests.llm.actions import Action, ActionBatch
from quests.refs import resolve_category_id, resolve_questline_id


class ActionExecError(Exception):
    def __init__(self, index: int, message: str) -> None:
        super().__init__(f"action[{index}]: {message}")
        self.index = index


@dataclass
class ActionResult:
    index: int
    action: str
    is_new: bool
    before: dict[str, Any] | None
    after: dict[str, Any]
    result: dict[str, Any] | None = None  # populated once actually written


def _placeholder_id(index: int) -> int:
    """Negative synthetic id for an entity that only exists in a dry-run preview."""
    return -(index + 1)


class ActionExecutor:
    def __init__(self, api_base: str) -> None:
        self.api_base = api_base.rstrip("/")

    def _api(
        self,
        method: str,
        path: str,
        *,
        query: dict[str, Any] | None = None,
        body: dict[str, Any] | None = None,
    ) -> Any:
        url = f"{self.api_base}{path}"
        if query:
            q = {k: v for k, v in query.items() if v is not None}
            if q:
                url = f"{url}?{urllib.parse.urlencode(q)}"
        data = None
        headers = {"Accept": "application/json"}
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(url, data=data, headers=headers, method=method.upper())
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = resp.read()
                return json.loads(raw.decode("utf-8")) if raw else None
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", errors="replace")
            try:
                detail = json.loads(detail).get("detail", detail)
            except json.JSONDecodeError:
                pass
            raise RuntimeError(f"API {e.code}: {detail}") from e
        except urllib.error.URLError as e:
            raise RuntimeError(f"cannot reach Quests API ({self.api_base}): {e.reason}") from e

    def _get(self, path: str, query: dict[str, Any] | None = None) -> Any:
        return self._api("GET", path, query=query)

    def _resolve_category(self, raw: str | None) -> int | None:
        return resolve_category_id(raw, api_get=self._get)

    def _resolve_questline(self, raw: str | None) -> int | None:
        return resolve_questline_id(raw, api_get=self._get)

    def run(self, batch: ActionBatch, *, dry_run: bool = True) -> list[ActionResult]:
        if batch.needs_clarification:
            raise ActionExecError(-1, batch.clarify_question or "needs clarification")
        results: list[ActionResult] = []
        for act in batch.actions:
            results.append(self._run_one(act, results, dry_run=dry_run))
        return results

    def _resolved_id(
        self,
        literal: int | None,
        ref_index: int | None,
        results: list[ActionResult],
        *,
        label: str,
    ) -> int | None:
        if ref_index is None:
            return literal
        if ref_index >= len(results):
            raise ActionExecError(ref_index, f"{label}_ref points to an unresolved action")
        r = results[ref_index]
        rid = (r.result or r.after).get("id")
        if rid is None:
            raise ActionExecError(ref_index, f"{label}_ref target has no id")
        return rid

    def _run_one(
        self, act: Action, results: list[ActionResult], *, dry_run: bool
    ) -> ActionResult:
        quest_id = self._resolved_id(act.quest_id, act.quest_id_ref, results, label="quest")
        questline_id = self._resolved_id(
            act.questline_id, act.questline_id_ref, results, label="questline"
        )

        if act.action == "create_questline":
            body: dict[str, Any] = {"title": act.title}
            for f in ("description", "color", "icon"):
                v = getattr(act, f)
                if v is not None:
                    body[f] = v
            cat_id = self._resolve_category(act.category)
            if cat_id is not None:
                body["category_id"] = cat_id
            if dry_run:
                return ActionResult(act.index, act.action, True, None, {"id": _placeholder_id(act.index), **body})
            q = self._api("POST", "/api/questlines", body=body)
            return ActionResult(act.index, act.action, True, None, q, result=q)

        if act.action == "create_quest":
            body = {"title": act.title}
            for f in (
                "description", "significance", "pinned", "sort_order",
                "deadline_at", "duration_seconds",
            ):
                v = getattr(act, f)
                if v is not None:
                    body[f] = v
            if questline_id is not None:
                body["questline_id"] = questline_id
            else:
                cat_id = self._resolve_category(act.category)
                if cat_id is not None:
                    body["category_id"] = cat_id
            if act.steps:
                body["steps"] = [s.model_dump() for s in act.steps]
            if dry_run:
                return ActionResult(act.index, act.action, True, None, {"id": _placeholder_id(act.index), **body})
            q = self._api("POST", "/api/quests", body=body)
            return ActionResult(act.index, act.action, True, None, q, result=q)

        if act.action == "add_step":
            if quest_id is not None and quest_id < 0:
                raise ActionExecError(
                    act.index,
                    "target quest only exists as a dry-run placeholder; "
                    "add_step on it is shown nested under that quest, not fetched",
                )
            before = self._get("/api/context", {"quest": quest_id})
            body: dict[str, Any] = {
                "title": act.title,
                "progress_total": act.progress_total or 1,
                "progress_current": act.progress_current or 0,
            }
            if act.description is not None:
                body["description"] = act.description
            if act.sort_order is not None:
                body["sort_order"] = act.sort_order
            if dry_run:
                return ActionResult(act.index, act.action, True, before, {**body, "quest_id": quest_id})
            q = self._api("POST", f"/api/quests/{quest_id}/steps", body=body)
            return ActionResult(act.index, act.action, True, before, q, result=q)

        if act.action == "update_quest":
            if quest_id is not None and quest_id < 0:
                raise ActionExecError(
                    act.index,
                    "target quest only exists as a dry-run placeholder; "
                    "fold this update into that create_quest action instead",
                )
            before = self._get("/api/context", {"quest": quest_id})
            body = {}
            for f in (
                "title", "description", "status", "significance", "pinned",
                "sort_order", "deadline_at", "duration_seconds",
            ):
                v = getattr(act, f)
                if v is not None:
                    body[f] = v
            if act.category_id is not None:
                body["category_id"] = act.category_id
            if act.clear_questline:
                body["questline_id"] = None
            elif questline_id is not None:
                body["questline_id"] = questline_id
            if not body:
                raise ActionExecError(act.index, "no fields to change")
            after = {"id": quest_id, **body}
            if dry_run:
                return ActionResult(act.index, act.action, False, before, after)
            q = self._api("PATCH", f"/api/quests/{quest_id}", body=body)
            return ActionResult(act.index, act.action, False, before, q, result=q)

        if act.action == "update_step":
            before = self._get("/api/context", {"step": act.step_id})
            body = {}
            for f in ("title", "description", "progress_current", "progress_total", "sort_order"):
                v = getattr(act, f)
                if v is not None:
                    body[f] = v
            if not body:
                raise ActionExecError(act.index, "no fields to change")
            after = {"quest_id": quest_id, "step_id": act.step_id, **body}
            if dry_run:
                return ActionResult(act.index, act.action, False, before, after)
            q = self._api(
                "PATCH", f"/api/quests/{quest_id}/steps/{act.step_id}", body=body
            )
            return ActionResult(act.index, act.action, False, before, q, result=q)

        if act.action == "delete_step":
            before = self._get("/api/context", {"step": act.step_id})
            after = {"quest_id": quest_id, "step_id": act.step_id, "deleted": True}
            if dry_run:
                return ActionResult(act.index, act.action, False, before, after)
            q = self._api("DELETE", f"/api/quests/{quest_id}/steps/{act.step_id}")
            return ActionResult(act.index, act.action, False, before, q, result=q)

        raise ActionExecError(act.index, f"unknown action {act.action!r}")
