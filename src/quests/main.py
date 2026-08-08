from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from quests.api import categories, context, events, health, hero, questlines, quests, templates
from quests.checks import run_due_step_checks
from quests.config import CORS_ORIGINS, HOST, PORT, RELOAD, ROOT
from quests.db import init_db
from quests.events import hub
from quests.expire import expire_overdue_quests
from quests.hero import decay_momentum
from quests.periodic import materialize_due
from quests.window_start import notify_window_starts

FRONTEND_DIST = ROOT / "frontend" / "dist"
EXPIRE_POLL_S = 15


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await init_db(seed=True)
    await hub.publish("startup", title="Quests", detail="server ready", toast=False, sound="")

    async def maintenance_loop() -> None:
        while True:
            try:
                await expire_overdue_quests()
            except Exception:
                pass
            try:
                await notify_window_starts()
            except Exception:
                pass
            try:
                await materialize_due()
            except Exception:
                pass
            try:
                await run_due_step_checks()
            except Exception:
                pass
            try:
                await decay_momentum()
            except Exception:
                pass
            await asyncio.sleep(EXPIRE_POLL_S)

    task = asyncio.create_task(maintenance_loop())
    try:
        yield
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


app = FastAPI(title="Quests", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(health.router)
app.include_router(events.router)
app.include_router(quests.router)
app.include_router(templates.router)
app.include_router(hero.router)
app.include_router(categories.router)
app.include_router(questlines.router)
app.include_router(context.router)


def _mount_spa() -> None:
    if not FRONTEND_DIST.is_dir():
        return

    assets = FRONTEND_DIST / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    @app.get("/")
    async def spa_index() -> FileResponse:
        return FileResponse(FRONTEND_DIST / "index.html")

    @app.get("/{full_path:path}")
    async def spa_fallback(full_path: str) -> FileResponse:
        if full_path.startswith("api/") or full_path in {"api", "ws", "docs", "openapi.json", "redoc"}:
            raise HTTPException(status_code=404, detail="Not Found")
        candidate = FRONTEND_DIST / full_path
        if candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(FRONTEND_DIST / "index.html")


_mount_spa()


def run() -> None:
    import uvicorn

    uvicorn.run("quests.main:app", host=HOST, port=PORT, reload=RELOAD)


if __name__ == "__main__":
    run()
