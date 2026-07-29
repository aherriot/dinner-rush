import os

# Test-isolation safety net — must run before anything under `dispatch` is
# imported. `DISPATCH_POSTGRES_DB` defaults to the exact same database name
# the live service uses (`dispatch`), and this session's `_schema` fixture
# below ends with `Base.metadata.drop_all(engine)`. A `uv run pytest`
# invocation that forgets to point `DISPATCH_POSTGRES_DB` somewhere else —
# or a `make test` run against a Postgres a `make up`'d demo is also using —
# will otherwise drop the live demo's own tables out from under it. Forcing
# a `_test` suffix here, unconditionally, means that can't happen regardless
# of how the suite is invoked.
_db_env_var = "DISPATCH_POSTGRES_DB"
_requested_db = os.environ.get(_db_env_var, "dispatch")
if not _requested_db.endswith("_test"):
    os.environ[_db_env_var] = f"{_requested_db}_test"

# Same hazard, Redis side: `test_assignment.py`/`test_board_endpoints.py`'s
# `redis_client` fixtures read `REDIS_URL` and their teardown unconditionally
# `DEL`s the shared `couriers:live` GEO key. Postgres gets its own isolated
# `_test` database above, but `REDIS_URL`'s default (`redis://localhost:6379/0`)
# is the exact same instance and DB index a `make up`'d demo's dispatch
# service uses — a bare `uv run pytest` with no override wipes every live
# courier's position out from under a running demo. Redis has no per-suite
# database name the way Postgres does, only a numeric index, so redirect to
# DB 15 (conventionally the "throwaway" index) whenever the URL still points
# at the un-overridden default DB 0; an explicitly-chosen non-zero index is
# left alone, same as the Postgres guard trusting an already-`_test`-suffixed
# name.
_redis_env_var = "REDIS_URL"
_requested_redis_url = os.environ.get(_redis_env_var, "redis://localhost:6379/0")
if _requested_redis_url.rstrip("/").rsplit("/", 1)[-1] in ("", "0"):
    os.environ[_redis_env_var] = _requested_redis_url.rstrip("/").rsplit("/", 1)[0] + "/15"

from collections.abc import Iterator  # noqa: E402

import psycopg  # noqa: E402
import pytest  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from dispatch import settings  # noqa: E402
from dispatch.db import Base, SessionLocal, engine  # noqa: E402

_TABLES = (
    "address_grant",
    "trip",
    "courier",
    "pending_dropoff",
    "outbox",
    "processed_event",
)


def _ensure_test_database_exists() -> None:
    """`CREATE DATABASE` can't run inside a transaction, and the target
    database has to exist before anything can connect to it — so this goes
    through Postgres's own always-present `postgres` maintenance database
    first, on the same server `settings` already points at."""
    conn = psycopg.connect(
        host=settings.POSTGRES_HOST,
        port=settings.POSTGRES_PORT,
        user=settings.POSTGRES_USER,
        password=settings.POSTGRES_PASSWORD,
        dbname="postgres",
        autocommit=True,
    )
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT 1 FROM pg_database WHERE datname = %s", (settings.POSTGRES_DB,))
            if cursor.fetchone() is None:
                cursor.execute(f'CREATE DATABASE "{settings.POSTGRES_DB}"')
    finally:
        conn.close()


@pytest.fixture(scope="session", autouse=True)
def _schema() -> Iterator[None]:
    _ensure_test_database_exists()
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)


@pytest.fixture
def session() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.rollback()
        db.close()


@pytest.fixture(autouse=True)
def _clean_tables() -> Iterator[None]:
    yield
    db = SessionLocal()
    try:
        for table in _TABLES:
            db.execute(text(f"TRUNCATE TABLE {table} CASCADE"))
        db.commit()
    finally:
        db.close()
