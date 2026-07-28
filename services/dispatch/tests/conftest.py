from collections.abc import Iterator

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from dispatch.db import Base, SessionLocal, engine

_TABLES = (
    "address_grant",
    "trip",
    "courier",
    "pending_dropoff",
    "outbox",
    "processed_event",
)


@pytest.fixture(scope="session", autouse=True)
def _schema() -> Iterator[None]:
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
