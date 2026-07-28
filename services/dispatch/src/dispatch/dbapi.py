"""The seam that makes `dinner_rush_core.outbox` reusable unmodified here
(ADR 0003) — it takes a plain DB-API cursor, and SQLAlchemy's session
exposes exactly that underneath its own connection wrapper.
"""

from typing import Any

from sqlalchemy.orm import Session


def raw_cursor(session: Session) -> Any:
    return session.connection().connection.cursor()
