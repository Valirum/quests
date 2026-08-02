"""Unix-socket IPC for the running overlay (hotkeys via niri spawn)."""

from __future__ import annotations

import os
import socket
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from gi.repository import GLib

SOCKET_PATH = Path(
    os.environ.get(
        "QUESTS_OVERLAY_SOCK",
        str(Path(os.environ.get("XDG_RUNTIME_DIR", "/tmp")) / "quests-overlay.sock"),
    )
)


@dataclass
class IpcServer:
    sock: socket.socket
    stop: threading.Event


def send_command(command: str, timeout: float = 1.5) -> str:
    if not SOCKET_PATH.exists():
        raise FileNotFoundError(
            f"Overlay socket not found: {SOCKET_PATH} (is the overlay running?)"
        )
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
        sock.settimeout(timeout)
        sock.connect(str(SOCKET_PATH))
        sock.sendall((command.strip() + "\n").encode())
        data = sock.recv(512)
    return data.decode().strip() or "ok"


def start_server(handler: Callable[[str], str]) -> IpcServer:
    """Listen for one-line commands; handler runs on the GTK main loop."""
    if SOCKET_PATH.exists():
        try:
            SOCKET_PATH.unlink()
        except OSError:
            pass

    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(str(SOCKET_PATH))
    server.listen(8)
    server.settimeout(1.0)

    stop = threading.Event()

    def loop() -> None:
        while not stop.is_set():
            try:
                conn, _ = server.accept()
            except TimeoutError:
                continue
            except OSError:
                break
            with conn:
                try:
                    raw = conn.recv(256).decode().strip().splitlines()
                    cmd = raw[0] if raw else ""
                except Exception:
                    cmd = ""

                box: dict[str, str | bool] = {"done": False, "reply": "error"}

                def apply() -> bool:
                    try:
                        box["reply"] = handler(cmd)
                    except Exception as exc:  # noqa: BLE001
                        box["reply"] = f"error: {exc}"
                    box["done"] = True
                    return False

                GLib.idle_add(apply)
                deadline = time.time() + 2.0
                while not box["done"] and time.time() < deadline:
                    time.sleep(0.01)
                try:
                    conn.sendall(str(box["reply"]).encode())
                except OSError:
                    pass

    thread = threading.Thread(target=loop, name="quests-overlay-ipc", daemon=True)
    thread.start()
    return IpcServer(sock=server, stop=stop)


def stop_server(server: IpcServer | None) -> None:
    if server is None:
        return
    server.stop.set()
    try:
        server.sock.close()
    except OSError:
        pass
    try:
        if SOCKET_PATH.exists():
            SOCKET_PATH.unlink()
    except OSError:
        pass
