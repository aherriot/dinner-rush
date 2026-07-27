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
COPY services/kitchen services/kitchen

RUN uv sync --frozen --no-dev --package kitchen --package dinner-rush-core

ENV PATH="/app/.venv/bin:${PATH}"
WORKDIR /app/services/kitchen

EXPOSE 8001

# uvicorn is the default CMD; `cli.py relay`/`stream_consumer` and the
# Celery worker override this via compose.yaml's `command:` on the same
# image — same pattern as the gateway image (services/gateway/Dockerfile).
CMD ["uvicorn", "kitchen.main:app", "--host", "0.0.0.0", "--port", "8001"]
