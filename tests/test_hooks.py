"""Unit tests for quests.hooks store + dispatch."""

from __future__ import annotations

import json
import socket
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

from quests import hooks as hooks_mod


@pytest.fixture()
def hooks_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "hooks.json"
    monkeypatch.setattr(hooks_mod, "HOOKS_PATH", path)
    return path


def test_expand_events_aliases():
    assert hooks_mod.expand_events(["complete"]) == ["quest_completed"]
    assert "step_completed" in hooks_mod.expand_events(["step"])
    assert "step_progress" in hooks_mod.expand_events(["on_step"])
    kinds = hooks_mod.expand_events(["status"])
    assert "quest_failed" in kinds
    assert "status_changed" in kinds


def test_expand_events_raw_and_dedupe():
    assert hooks_mod.expand_events(["quest_completed", "complete"]) == ["quest_completed"]
    assert hooks_mod.expand_events(["custom_kind"]) == ["custom_kind"]


def test_add_list_remove_roundtrip(hooks_file: Path):
    h = hooks_mod.add_hook(
        events=["complete"],
        hook_type="script",
        command="true",
        name="n1",
    )
    assert h.id
    assert h.quest_id is None
    assert hooks_mod.load_hooks() == [h] or hooks_mod.load_hooks()[0].id == h.id

    qh = hooks_mod.add_hook(
        events=["step"],
        hook_type="script",
        command="true",
        quest_id=7,
    )
    assert qh.quest_id == 7
    assert len(hooks_mod.load_hooks()) == 2

    got = hooks_mod.get_hook(h.id)
    assert got is not None
    assert got.name == "n1"

    by_name = hooks_mod.get_hook("n1")
    assert by_name is not None and by_name.id == h.id

    hooks_mod.set_hook_enabled(h.id, False)
    assert hooks_mod.get_hook(h.id).enabled is False

    removed = hooks_mod.remove_hook(h.id)
    assert removed is not None
    assert len(hooks_mod.load_hooks()) == 1
    assert hooks_mod.get_hook(h.id) is None


def test_add_hook_validation(hooks_file: Path):
    with pytest.raises(ValueError, match="event"):
        hooks_mod.add_hook(events=[], hook_type="script", command="true")
    with pytest.raises(ValueError, match="command"):
        hooks_mod.add_hook(events=["complete"], hook_type="script", command="")
    with pytest.raises(ValueError, match="url"):
        hooks_mod.add_hook(events=["complete"], hook_type="webhook", url="")
    with pytest.raises(ValueError, match="path"):
        hooks_mod.add_hook(events=["complete"], hook_type="socket", path="")


def test_matches_global_vs_quest(hooks_file: Path):
    g = hooks_mod.add_hook(events=["complete"], hook_type="script", command="true")
    q = hooks_mod.add_hook(
        events=["complete"], hook_type="script", command="true", quest_id=3
    )

    assert g.matches("quest_completed", 99)
    assert g.matches("quest_completed", None)
    assert not g.matches("step_completed", 1)

    assert q.matches("quest_completed", 3)
    assert not q.matches("quest_completed", 4)
    assert not q.matches("quest_completed", None)


def test_dispatch_script_writes_file(hooks_file: Path, tmp_path: Path):
    out = tmp_path / "out.txt"
    hooks_mod.add_hook(
        events=["complete"],
        hook_type="script",
        command=f'printf "%s|%s" "$QUESTS_KIND" "$QUESTS_TITLE" > "{out}"',
    )
    n = hooks_mod.dispatch_hooks_sync(
        {"kind": "quest_completed", "quest_id": 1, "title": "Herb", "detail": ""}
    )
    assert n == 1
    assert out.read_text(encoding="utf-8") == "quest_completed|Herb"


def test_dispatch_script_stdin_json(hooks_file: Path, tmp_path: Path):
    out = tmp_path / "payload.json"
    hooks_mod.add_hook(
        events=["step"],
        hook_type="script",
        command=f'cat > "{out}"',
        quest_id=5,
    )
    event = {
        "kind": "step_completed",
        "quest_id": 5,
        "title": "Q",
        "detail": "step",
    }
    assert hooks_mod.dispatch_hooks_sync(event) == 1
    raw = out.read_text(encoding="utf-8").strip()
    assert json.loads(raw)["kind"] == "step_completed"

    # wrong quest → no run
    assert hooks_mod.dispatch_hooks_sync({**event, "quest_id": 9}) == 0


def test_dispatch_skips_disabled_and_startup(hooks_file: Path, tmp_path: Path):
    out = tmp_path / "x"
    h = hooks_mod.add_hook(
        events=["complete"],
        hook_type="script",
        command=f'echo hi > "{out}"',
    )
    hooks_mod.set_hook_enabled(h.id, False)
    assert hooks_mod.dispatch_hooks_sync(
        {"kind": "quest_completed", "quest_id": 1, "title": "t"}
    ) == 0
    assert not out.exists()
    assert hooks_mod.dispatch_hooks_sync({"kind": "startup", "title": "x"}) == 0


def test_dispatch_webhook(hooks_file: Path):
    received: list[dict] = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):  # noqa: N802
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length)
            received.append(json.loads(body.decode("utf-8")))
            self.send_response(200)
            self.end_headers()

        def log_message(self, *_args):
            return

    server = HTTPServer(("127.0.0.1", 0), Handler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        hooks_mod.add_hook(
            events=["fail"],
            hook_type="webhook",
            url=f"http://127.0.0.1:{port}/hook",
        )
        n = hooks_mod.dispatch_hooks_sync(
            {"kind": "quest_failed", "quest_id": 2, "title": "Boom", "detail": "x"}
        )
        assert n == 1
        assert received and received[0]["title"] == "Boom"
    finally:
        server.shutdown()


def test_dispatch_socket(hooks_file: Path, tmp_path: Path):
    sock_path = tmp_path / "hooks.sock"
    got: list[str] = []

    def serve() -> None:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as srv:
            srv.bind(str(sock_path))
            srv.listen(1)
            srv.settimeout(2)
            conn, _ = srv.accept()
            with conn:
                got.append(conn.recv(4096).decode("utf-8"))

    t = threading.Thread(target=serve, daemon=True)
    t.start()
    # Wait until socket file exists
    for _ in range(50):
        if sock_path.exists():
            break
        t.join(0.01)

    hooks_mod.add_hook(
        events=["created"],
        hook_type="socket",
        path=str(sock_path),
    )
    n = hooks_mod.dispatch_hooks_sync(
        {"kind": "quest_created", "quest_id": 8, "title": "New", "detail": ""}
    )
    t.join(timeout=2)
    assert n == 1
    assert got
    assert json.loads(got[0].strip())["title"] == "New"
