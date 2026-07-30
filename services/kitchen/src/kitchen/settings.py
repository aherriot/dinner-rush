"""Kitchen's own settings — its own Postgres, never a front-of-house connection
string (CLAUDE.md §5).

`KITCHEN_POSTGRES_*` rather than the bare `POSTGRES_*` front-of-house uses: inside
Docker each service has its own isolated environment so it wouldn't matter,
but a single `uv run pytest` at the repo root runs front-of-house's and kitchen's
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

# Front-of-house is the only JWT signer (SPEC.md §6.3) — kitchen fetches and caches
# its public key from here rather than sharing a secret.
FRONT_OF_HOUSE_URL = os.environ.get("FRONT_OF_HOUSE_URL", "http://front-of-house:8000")
JWKS_URL = f"{FRONT_OF_HOUSE_URL}/.well-known/jwks.json"
