"""Store and serve per-questline custom icon images."""

from __future__ import annotations

import re
from pathlib import Path

from fastapi import HTTPException, UploadFile, status

from quests.config import DATA_DIR

ICON_DIR = DATA_DIR / "questline-icons"
MAX_BYTES = 512 * 1024
_SAFE_NAME = re.compile(r"^[A-Za-z0-9._-]+$")

ALLOWED_TYPES: dict[str, str] = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/webp": ".webp",
    "image/gif": ".gif",
    "image/svg+xml": ".svg",
}


def ensure_icon_dir() -> Path:
    ICON_DIR.mkdir(parents=True, exist_ok=True)
    return ICON_DIR


def icon_file_path(filename: str) -> Path:
    name = Path(filename).name
    if not name or not _SAFE_NAME.match(name):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid icon filename"
        )
    path = (ICON_DIR / name).resolve()
    if path.parent != ICON_DIR.resolve():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid icon path"
        )
    return path


def icon_url(line_id: int, *, version: str | None = None) -> str:
    url = f"/api/questlines/{line_id}/icon"
    if version:
        url = f"{url}?v={version}"
    return url


def delete_icon_file(filename: str | None) -> None:
    if not filename:
        return
    try:
        path = icon_file_path(filename)
    except HTTPException:
        return
    if path.is_file():
        path.unlink()


async def save_uploaded_icon(line_id: int, upload: UploadFile) -> str:
    content_type = (upload.content_type or "").split(";")[0].strip().lower()
    ext = ALLOWED_TYPES.get(content_type)
    if not ext:
        # fallback by filename
        suffix = Path(upload.filename or "").suffix.lower()
        if suffix in {".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg"}:
            ext = ".jpg" if suffix == ".jpeg" else suffix
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Unsupported image type (png/jpeg/webp/gif/svg)",
            )

    raw = await upload.read()
    if not raw:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Empty icon file"
        )
    if len(raw) > MAX_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Icon too large (max {MAX_BYTES // 1024} KiB)",
        )

    ensure_icon_dir()
    filename = f"{line_id}{ext}"
    path = icon_file_path(filename)
    # Drop previous variants for this line (other extensions).
    for old in ICON_DIR.glob(f"{line_id}.*"):
        if old.resolve() != path and old.is_file():
            old.unlink()
    path.write_bytes(raw)
    return filename
