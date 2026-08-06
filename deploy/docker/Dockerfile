# syntax=docker/dockerfile:1

# --- Frontend (Vite / Svelte) ---
FROM node:22-bookworm-slim AS frontend
WORKDIR /src/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# --- Python deps ---
FROM python:3.12-slim-bookworm AS python-base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    PATH="/app/.venv/bin:$PATH" \
    QUESTS_ROOT=/app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
COPY alembic ./alembic
COPY alembic.ini ./

RUN uv sync --locked --no-dev

# --- API runtime (serves SPA from frontend/dist) ---
FROM python-base AS api
COPY --from=frontend /src/frontend/dist /app/frontend/dist
COPY deploy/docker/entrypoint-api.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
EXPOSE 8765
VOLUME ["/app/data"]
ENTRYPOINT ["/entrypoint.sh"]
CMD ["quests-server"]

# --- Telegram bot (same image lineage) ---
FROM python-base AS bot
COPY deploy/docker/entrypoint-bot.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
VOLUME ["/app/data"]
ENTRYPOINT ["/entrypoint.sh"]
CMD ["quests-telegram"]
