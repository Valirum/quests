"""Speech-to-text via faster-whisper (default: small, Russian)."""

from __future__ import annotations

import asyncio
import logging
import os
import threading
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger("quests.stt")

# Short aliases → HuggingFace / faster-whisper model ids.
MODEL_ALIASES: dict[str, str] = {
    "tiny": "tiny",
    "base": "base",
    "small": "small",
    "medium": "medium",
    "large": "large-v3",
    "large-v2": "large-v2",
    "large-v3": "large-v3",
    "distil-large-v3": "distil-large-v3",
}

DEFAULT_MODEL = "small"
DEFAULT_DEVICE = "cpu"
DEFAULT_COMPUTE = "int8"
DEFAULT_LANGUAGE = "ru"


@dataclass(frozen=True)
class SttSettings:
    model: str
    device: str
    compute_type: str
    language: str | None


def normalize_whisper_model(raw: str) -> str:
    """Map small/medium/large (and friends) to a concrete model id."""
    key = (raw or DEFAULT_MODEL).strip().lower()
    if not key:
        key = DEFAULT_MODEL
    if key in MODEL_ALIASES:
        return MODEL_ALIASES[key]
    # Allow full Systran/faster-whisper-* ids or other HF names as-is.
    return raw.strip()


def load_stt_settings() -> SttSettings:
    lang = (os.environ.get("QUESTS_WHISPER_LANGUAGE") or DEFAULT_LANGUAGE).strip()
    return SttSettings(
        model=normalize_whisper_model(
            os.environ.get("QUESTS_WHISPER_MODEL") or DEFAULT_MODEL
        ),
        device=(os.environ.get("QUESTS_WHISPER_DEVICE") or DEFAULT_DEVICE).strip(),
        compute_type=(
            os.environ.get("QUESTS_WHISPER_COMPUTE") or DEFAULT_COMPUTE
        ).strip(),
        language=None if lang in {"", "auto"} else lang,
    )


class SttError(Exception):
    pass


class WhisperStt:
    """Lazy singleton wrapper around faster-whisper."""

    def __init__(self) -> None:
        self._model = None
        self._lock = threading.Lock()
        self._settings: SttSettings | None = None

    def _ensure_model(self, settings: SttSettings):
        with self._lock:
            if self._model is not None and self._settings == settings:
                return self._model
            try:
                from faster_whisper import WhisperModel
            except ImportError as e:
                raise SttError(
                    "faster-whisper не установлен (uv sync / uv add faster-whisper)"
                ) from e
            log.info(
                "loading whisper model=%s device=%s compute=%s",
                settings.model,
                settings.device,
                settings.compute_type,
            )
            self._model = WhisperModel(
                settings.model,
                device=settings.device,
                compute_type=settings.compute_type,
            )
            self._settings = settings
            return self._model

    def transcribe_file(self, path: str | Path, *, settings: SttSettings | None = None) -> str:
        settings = settings or load_stt_settings()
        path = Path(path)
        if not path.is_file():
            raise SttError(f"файл не найден: {path}")
        model = self._ensure_model(settings)
        # Smaller models on CPU: beam 1 is much faster, quality still OK for short voice notes.
        beam = 1 if settings.model in {"tiny", "base", "small"} else 5
        try:
            segments, info = model.transcribe(
                str(path),
                language=settings.language,
                vad_filter=True,
                beam_size=beam,
            )
            parts = [seg.text.strip() for seg in segments if seg.text and seg.text.strip()]
        except Exception as e:
            raise SttError(f"whisper failed: {e}") from e
        text = " ".join(parts).strip()
        log.info(
            "stt ok model=%s lang=%s duration≈%s chars=%s",
            settings.model,
            getattr(info, "language", "?"),
            getattr(info, "duration", "?"),
            len(text),
        )
        if not text:
            raise SttError("пустая расшифровка (тишина или неразборчиво)")
        return text

    async def transcribe_file_async(
        self, path: str | Path, *, settings: SttSettings | None = None
    ) -> str:
        return await asyncio.to_thread(self.transcribe_file, path, settings=settings)


_stt: WhisperStt | None = None


def get_stt() -> WhisperStt:
    global _stt
    if _stt is None:
        _stt = WhisperStt()
    return _stt
