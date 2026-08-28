"""Quests CLI launcher → Go binary ``go/bin/quests``.

Native Python remains only for ``llm-add`` (``QUESTS_CLI_NATIVE=1``).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from quests.config import HOST, PORT

API_BASE = (os.environ.get("QUESTS_API") or f"http://{HOST}:{PORT}").rstrip("/")


class CliError(Exception):
    def __init__(self, message: str, code: int = 1) -> None:
        super().__init__(message)
        self.code = code


def emit(data: Any, *, as_json: bool, text: str | None = None) -> None:
    if as_json:
        print(json.dumps(data, ensure_ascii=False, indent=2, default=str))
    elif text is not None:
        print(text)
    else:
        print(data)


def emit_error(message: str, *, as_json: bool, code: int = 1) -> int:
    if as_json:
        print(
            json.dumps({"ok": False, "error": message}, ensure_ascii=False),
            file=sys.stderr,
        )
    else:
        print(f"error: {message}", file=sys.stderr)
    return code


def api_request(
    method: str,
    path: str,
    *,
    body: dict[str, Any] | None = None,
    query: dict[str, Any] | None = None,
) -> Any:
    url = f"{API_BASE}{path}"
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
            if not raw:
                return None
            return json.loads(raw.decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(detail)
            detail = parsed.get("detail", detail)
        except json.JSONDecodeError:
            pass
        raise CliError(f"API {e.code}: {detail}") from e
    except urllib.error.URLError as e:
        raise CliError(
            f"не удалось связаться с API ({API_BASE}): {e.reason}. "
            "Запусти сервер: ./scripts/run-server.sh"
        ) from e


def cmd_llm_add(ns: argparse.Namespace) -> int:
    """Free-form text → LLM draft → POST /api/quests."""
    from quests.llm import (
        LlmError,
        draft_to_create_body,
        extract_quest_draft_sync,
        format_draft_preview,
    )
    from quests.llm.config import load_llm_settings

    text = " ".join(ns.text).strip() if isinstance(ns.text, list) else str(ns.text).strip()
    if not text:
        raise CliError("нужен текст описания")

    settings = load_llm_settings()
    if not bool(getattr(ns, "json", False)):
        if settings.provider == "cursor":
            print(f"Cursor ({settings.model})…", file=sys.stderr)
        elif settings.provider == "groq":
            print(f"Groq ({settings.model})…", file=sys.stderr)
        else:
            print(
                f"Ollama ({settings.model} @ {settings.base_url})…",
                file=sys.stderr,
            )
    try:
        bundle = extract_quest_draft_sync(text, settings=settings)
    except LlmError as e:
        raise CliError(str(e)) from e

    as_json = bool(getattr(ns, "json", False))
    if bundle.needs_clarification and (bundle.clarify_question or "").strip():
        draft = bundle.primary
        if as_json:
            emit(
                {
                    "ok": False,
                    "needs_clarification": True,
                    "question": bundle.clarify_question,
                    "draft": draft.model_dump(),
                    "variations": [d.model_dump() for d in bundle.variations],
                },
                as_json=True,
            )
            return 2
        print(format_draft_preview(draft, index=0, total=len(bundle.variations)))
        print(f"\nуточнение: {bundle.clarify_question}", file=sys.stderr)
        return 2

    pick = max(0, int(getattr(ns, "variant", 0) or 0))
    pick = min(pick, len(bundle.variations) - 1)
    draft = bundle.variations[pick]
    cats = api_request("GET", "/api/categories") or []
    body = draft_to_create_body(draft, categories=cats)

    if not bool(getattr(ns, "yes", False)) and not as_json:
        for i, d in enumerate(bundle.variations):
            mark = "→ " if i == pick else "  "
            print(mark + format_draft_preview(d, index=i, total=len(bundle.variations)))
            print()
        try:
            ans = input(f"создать вариант {pick + 1}? [y/N] ").strip().lower()
        except EOFError:
            ans = ""
        if ans not in {"y", "yes", "д", "да"}:
            print("отменено")
            return 1

    q = api_request("POST", "/api/quests", body=body)
    if as_json:
        emit(
            {
                "ok": True,
                "draft": draft.model_dump(),
                "variations": [d.model_dump() for d in bundle.variations],
                "picked": pick,
                "quest": q,
            },
            as_json=True,
        )
    else:
        print(f"создан #{q['id']}: {q['title']}")
    return 0


def _llm_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="quests llm-add")
    p.add_argument("--json", action="store_true")
    p.add_argument("--api", default=None)
    p.add_argument("text", nargs="+")
    p.add_argument("-y", "--yes", action="store_true")
    p.add_argument("--variant", type=int, default=0)
    return p


def _fmt_action_line(r: Any) -> str:
    tag = "NEW " if r.is_new else "EDIT"
    after = {k: v for k, v in r.after.items() if k != "id"}
    return f"  [{tag}] #{r.index} {r.action} id={r.after.get('id')} {after}"


def cmd_llm_action(ns: argparse.Namespace) -> int:
    """Free-form text → LLM action batch → dry-run preview → confirm → execute."""
    from quests.actions_exec import ActionExecError, ActionExecutor
    from quests.llm import LlmError, extract_action_batch_sync
    from quests.llm.config import load_llm_settings

    text = " ".join(ns.text).strip() if isinstance(ns.text, list) else str(ns.text).strip()
    if not text:
        raise CliError("нужен текст запроса")

    settings = load_llm_settings()
    as_json = bool(getattr(ns, "json", False))
    if not as_json:
        print(f"Groq ({settings.model})…", file=sys.stderr)

    try:
        batch = extract_action_batch_sync(text, settings=settings)
    except LlmError as e:
        raise CliError(str(e)) from e

    if batch.needs_clarification:
        if as_json:
            emit({"ok": False, "needs_clarification": True, "question": batch.clarify_question}, as_json=True)
        else:
            print(f"уточнение: {batch.clarify_question}", file=sys.stderr)
        return 2

    executor = ActionExecutor(API_BASE)
    try:
        preview = executor.run(batch, dry_run=True)
    except ActionExecError as e:
        raise CliError(str(e)) from e

    if not as_json:
        print("план:")
        for r in preview:
            print(_fmt_action_line(r))
        if not bool(getattr(ns, "yes", False)):
            try:
                ans = input("применить? [y/N] ").strip().lower()
            except EOFError:
                ans = ""
            if ans not in {"y", "yes", "д", "да"}:
                print("отменено")
                return 1

    try:
        applied = executor.run(batch, dry_run=False)
    except ActionExecError as e:
        raise CliError(str(e)) from e

    if as_json:
        emit(
            {
                "ok": True,
                "preview": [
                    {"index": r.index, "action": r.action, "is_new": r.is_new, "after": r.after}
                    for r in preview
                ],
                "results": [
                    {"index": r.index, "action": r.action, "result": r.result} for r in applied
                ],
            },
            as_json=True,
        )
    else:
        for r in applied:
            print(_fmt_action_line(r))
    return 0


def _preview_payload(r: Any) -> dict[str, Any]:
    return {"index": r.index, "action": r.action, "is_new": r.is_new, "before": r.before, "after": r.after}


def cmd_llm_action_preview(ns: argparse.Namespace) -> int:
    """Free-form text → LLM action batch → dry-run preview, no writes. --json only.

    Called from the Go HTTP layer (POST /api/llm/actions/preview) as well as
    directly. Returns the raw batch alongside the preview so the caller can
    send that *exact* batch back to llm-action-apply — the model is not
    re-invoked between preview and apply, so what's shown is what runs.
    """
    from quests.actions_exec import ActionExecError, ActionExecutor
    from quests.llm import LlmError, extract_action_batch_sync

    text = " ".join(ns.text).strip() if isinstance(ns.text, list) else str(ns.text).strip()
    if not text:
        raise CliError("нужен текст запроса")

    try:
        batch = extract_action_batch_sync(text)
    except LlmError as e:
        raise CliError(str(e)) from e

    as_json = bool(getattr(ns, "json", False))
    if batch.needs_clarification:
        payload = {
            "ok": False,
            "needs_clarification": True,
            "clarify_question": batch.clarify_question,
        }
        emit(payload, as_json=True) if as_json else print(
            f"уточнение: {batch.clarify_question}", file=sys.stderr
        )
        return 2

    executor = ActionExecutor(API_BASE)
    try:
        preview = executor.run(batch, dry_run=True)
    except ActionExecError as e:
        raise CliError(str(e)) from e

    emit(
        {
            "ok": True,
            "needs_clarification": False,
            "batch": batch.model_dump(),
            "preview": [_preview_payload(r) for r in preview],
        },
        as_json=True,
    )
    return 0


def cmd_llm_action_apply(ns: argparse.Namespace) -> int:
    """Take a previously previewed batch (JSON on stdin) and execute it for real."""
    from pydantic import ValidationError

    from quests.actions_exec import ActionExecError, ActionExecutor
    from quests.llm.actions import ActionBatch

    raw = sys.stdin.read()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise CliError(f"батч не JSON: {e}") from e
    try:
        batch = ActionBatch.model_validate(data)
    except ValidationError as e:
        raise CliError(f"батч не прошёл валидацию: {e}") from e

    executor = ActionExecutor(API_BASE)
    try:
        applied = executor.run(batch, dry_run=False)
    except ActionExecError as e:
        raise CliError(str(e)) from e

    emit(
        {
            "ok": True,
            "results": [
                {"index": r.index, "action": r.action, "result": r.result} for r in applied
            ],
        },
        as_json=True,
    )
    return 0


def _llm_action_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="quests llm-action")
    p.add_argument("--json", action="store_true")
    p.add_argument("--api", default=None)
    p.add_argument("text", nargs="+")
    p.add_argument("-y", "--yes", action="store_true")
    return p


def _llm_action_preview_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="quests llm-action-preview")
    p.add_argument("--json", action="store_true")
    p.add_argument("--api", default=None)
    p.add_argument("text", nargs="+")
    return p


def _llm_action_apply_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="quests llm-action-apply")
    p.add_argument("--json", action="store_true")
    p.add_argument("--api", default=None)
    return p


def main(argv: list[str] | None = None) -> int:
    from quests.envload import load_dotenv_files

    load_dotenv_files()
    argv_list = list(sys.argv[1:] if argv is None else argv)

    if os.environ.get("QUESTS_CLI_NATIVE") != "1":
        return _exec_go_cli(argv_list)

    return _main_llm_add(argv_list)


def _exec_go_cli(argv_list: list[str]) -> int:
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    binary = Path(os.environ.get("QUESTS_CLI_BIN") or root / "go" / "bin" / "quests")
    env = os.environ.copy()
    env.setdefault("QUESTS_ROOT", str(root))
    if not binary.is_file():
        build = root / "scripts" / "build-cli.sh"
        if build.is_file():
            import subprocess

            subprocess.check_call([str(build)], env=env)
        if not binary.is_file():
            print(
                f"error: Go CLI binary not found at {binary}; run ./scripts/build-cli.sh",
                file=sys.stderr,
            )
            return 1
    os.execvpe(str(binary), [str(binary), *argv_list], env)
    return 1


def _main_llm_add(argv_list: list[str]) -> int:
    # Strip leading subcommand when Go shells: python -m quests.cli <cmd> …
    kind = argv_list[0] if argv_list else ""
    if kind in {"llm-add", "add-llm", "new-llm", "llm-action", "action", "llm-action-preview", "llm-action-apply"}:
        argv_list = argv_list[1:]

    if kind == "llm-action-preview":
        parser = _llm_action_preview_parser()
        runner = cmd_llm_action_preview
    elif kind == "llm-action-apply":
        parser = _llm_action_apply_parser()
        runner = cmd_llm_action_apply
    elif kind in {"llm-action", "action"}:
        parser = _llm_action_parser()
        runner = cmd_llm_action
    else:
        parser = _llm_parser()
        runner = cmd_llm_add

    try:
        args = parser.parse_args(argv_list)
    except SystemExit as e:
        return int(e.code or 0)

    global API_BASE
    if args.api:
        API_BASE = str(args.api).rstrip("/")

    try:
        return int(runner(args) or 0)
    except CliError as e:
        return emit_error(str(e), as_json=bool(args.json), code=e.code)
    except BrokenPipeError:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
