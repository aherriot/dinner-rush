from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from dispatch import settings

engine = create_engine(settings.DATABASE_URL, pool_size=10, max_overflow=20)
# expire_on_commit=False: Celery tasks read attributes off an ORM object
# right after committing (to schedule the next step) — the default would
# force a refresh query against a session that's about to close.
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_session() -> Iterator[Session]:
    """FastAPI dependency — one session per request, closed after."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
