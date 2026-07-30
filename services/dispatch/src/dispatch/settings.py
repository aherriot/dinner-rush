"""Dispatch's own settings — its own Postgres, never a front-of-house connection
string (CLAUDE.md §5).

`DISPATCH_POSTGRES_*` rather than the bare `POSTGRES_*` front-of-house uses, same
reasoning as kitchen's `settings.py`: a single `uv run pytest` at the repo
root runs front-of-house's, kitchen's and dispatch's tests in one process against
three different Postgres servers at once, and they need distinct env var
names to all be reachable simultaneously.
"""

import os

POSTGRES_HOST = os.environ.get("DISPATCH_POSTGRES_HOST", "dispatch-db")
POSTGRES_PORT = os.environ.get("DISPATCH_POSTGRES_PORT", "5432")
POSTGRES_DB = os.environ.get("DISPATCH_POSTGRES_DB", "dispatch")
POSTGRES_USER = os.environ.get("DISPATCH_POSTGRES_USER", "dispatch")
POSTGRES_PASSWORD = os.environ.get("DISPATCH_POSTGRES_PASSWORD", "dispatch")

DATABASE_URL = os.environ.get(
    "DISPATCH_DATABASE_URL",
    f"postgresql+psycopg://{POSTGRES_USER}:{POSTGRES_PASSWORD}"
    f"@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}",
)

REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379/0")
CELERY_BROKER_URL = REDIS_URL

# Front-of-house is the only JWT signer (SPEC.md §6.3) — dispatch fetches and caches
# its public key from here rather than sharing a secret.
FRONT_OF_HOUSE_URL = os.environ.get("FRONT_OF_HOUSE_URL", "http://front-of-house:8000")
JWKS_URL = f"{FRONT_OF_HOUSE_URL}/.well-known/jwks.json"

COURIERS_GEO_KEY = "couriers:live"
