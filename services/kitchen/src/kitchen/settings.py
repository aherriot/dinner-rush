"""Kitchen's own settings — its own Postgres, never a gateway connection
string (CLAUDE.md §5).

`KITCHEN_POSTGRES_*` rather than the bare `POSTGRES_*` gateway uses: inside
Docker each service has its own isolated environment so it wouldn't matter,
but a single `uv run pytest` at the repo root runs gateway's and kitchen's
tests in one process against two different Postgres servers at once, and
they need distinct env var names to both be reachable simultaneously.
"""

import os

POSTGRES_HOST = os.environ.get("KITCHEN_POSTGRES_HOST", "kitchen-db")
POSTGRES_PORT = os.environ.get("KITCHEN_POSTGRES_PORT", "5432")
POSTGRES_DB = os.environ.get("KITCHEN_POSTGRES_DB", "kitchen")
POSTGRES_USER = os.environ.get("KITCHEN_POSTGRES_USER", "kitchen")
POSTGRES_PASSWORD = os.environ.get("KITCHEN_POSTGRES_PASSWORD", "kitchen")

DATABASE_URL = os.environ.get(
    "KITCHEN_DATABASE_URL",
    f"postgresql+psycopg://{POSTGRES_USER}:{POSTGRES_PASSWORD}"
    f"@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}",
)

REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379/0")
CELERY_BROKER_URL = REDIS_URL
