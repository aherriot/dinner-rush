FROM python:3.13.14-slim AS base

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.11.32 /uv /uvx /usr/local/bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml uv.lock .python-version ./
COPY packages/dinner_rush_core packages/dinner_rush_core
COPY services/gateway services/gateway

RUN uv sync --frozen --no-dev --package gateway --package dinner-rush-core

ENV PATH="/app/.venv/bin:${PATH}"
WORKDIR /app/services/gateway

EXPOSE 8000

# Daphne, not `runserver` — Phase 3 adds a real websocket route
# (/ws/orders/{code}), and `manage.py relay`/`stream_consumer`/celery worker
# override this CMD via compose.yaml's `command:` on the same image.
CMD ["daphne", "-b", "0.0.0.0", "-p", "8000", "gateway.asgi:application"]
