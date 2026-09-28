# syntax=docker/dockerfile:1

# --- Frontend (Vite / Svelte) ---
FROM node:22-bookworm-slim AS frontend
WORKDIR /src/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# --- Go API (+ CLI) ---
FROM golang:1.26-bookworm AS go-build
WORKDIR /src
COPY go/go.mod go/go.sum ./
RUN go mod download
COPY go/ ./
RUN CGO_ENABLED=0 go build -trimpath -ldflags="-s -w" -o /out/quests-server ./cmd/quests-server \
 && CGO_ENABLED=0 go build -trimpath -ldflags="-s -w" -o /out/quests ./cmd/quests

# --- Python (migrations + bot tooling) ---
FROM python:3.12-slim-bookworm AS python-base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    PATH="/app/.venv/bin:$PATH" \
    QUESTS_ROOT=/app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       curl ca-certificates \
       libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz-subset0 \
       fonts-dejavu-core fontconfig \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
COPY alembic ./alembic
COPY alembic.ini ./

# Core only (alembic/sqlmodel/dotenv) — api needs nothing heavier than this;
# the action-batch assistant is pure Go now (go/internal/llmassist).
RUN uv sync --locked --no-dev

# --- API runtime: Go server + SPA + Alembic migrate ---
FROM python-base AS api
RUN uv sync --locked --no-dev --extra pdf
COPY --from=go-build /out/quests-server /usr/local/bin/quests-server
COPY --from=go-build /out/quests /usr/local/bin/quests
COPY --from=frontend /src/frontend/dist /app/frontend/dist
COPY deploy/docker/entrypoint-api.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
ENV QUESTS_HOST=0.0.0.0 \
    QUESTS_PORT=8765 \
    QUESTS_ROOT=/app \
    QUESTS_DATA_DIR=/app/data
EXPOSE 8765
VOLUME ["/app/data"]
ENTRYPOINT ["/entrypoint.sh"]
CMD ["quests-server"]

# --- Telegram bot: aiogram only — STT lives in its own image/container ---
FROM python-base AS bot
RUN uv sync --locked --no-dev --extra bot
COPY deploy/docker/entrypoint-bot.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
VOLUME ["/app/data"]
ENTRYPOINT ["/entrypoint.sh"]
CMD ["quests-telegram"]

# --- STT sidecar: faster-whisper (ctranslate2/onnxruntime/av) isolated here
# so it only rebuilds/redownloads when STT itself changes, not on every
# aiogram bump. Bot talks to it over HTTP (quests.telegram.sttclient). ---
FROM python-base AS stt
RUN uv sync --locked --no-dev --extra stt
COPY deploy/docker/entrypoint-stt.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
ENV QUESTS_STT_HOST=0.0.0.0 \
    QUESTS_STT_PORT=8766 \
    HF_HOME=/app/data/hf-cache
EXPOSE 8766
# Whisper model weights download here on first use (faster-whisper → HF
# cache, redirected into the volume via HF_HOME) — a redeploy/restart then
# doesn't refetch them.
VOLUME ["/app/data"]
ENTRYPOINT ["/entrypoint.sh"]
CMD ["quests-stt"]

# ci: rebuild hook 2026-09-21T15:39Z
