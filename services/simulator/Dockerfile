FROM python:3.13.14-slim AS base

COPY --from=ghcr.io/astral-sh/uv:0.11.32 /uv /uvx /usr/local/bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml uv.lock .python-version ./
COPY services/simulator services/simulator

# No `--package dinner-rush-core` — the simulator is an ordinary API client
# (CLAUDE.md §5) with its own dependency file and no shared domain imports.
# This image never copies `packages/dinner_rush_core` or any `services/`
# directory but its own, so that isn't just a convention, it's structural.
RUN uv sync --frozen --no-dev --package simulator

ENV PATH="/app/.venv/bin:${PATH}"
WORKDIR /app/services/simulator

# No EXPOSE — standalone client, no ports (repo layout table, CLAUDE.md §3).
CMD ["python", "-m", "simulator.cli"]
