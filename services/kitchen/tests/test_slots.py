"""The portfolio piece (DECISIONS.md §0002): N concurrent claims on the last
free slot, exactly one winner, zero overbooking — run 200 times in CI.
"""

import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from kitchen.db import SessionLocal
from kitchen.models import Oven, OvenSlot
from kitchen.slots import claim_slot, count_occupied_slots, reap_stuck_slots, release_slot


def _make_oven(session: Session, *, slot_count: int) -> uuid.UUID:
    oven = Oven(name="Test Oven", slot_count=slot_count, status="available")
    session.add(oven)
    session.flush()
    for slot_index in range(slot_count):
        session.add(OvenSlot(oven_id=oven.id, slot_index=slot_index))
    session.commit()
    return oven.id


@pytest.fixture
def oven_with_one_free_slot(session: Session) -> uuid.UUID:
    return _make_oven(session, slot_count=1)


def _claim_in_its_own_session(order_id: uuid.UUID) -> bool:
    """Each concurrent claimer gets its own session/connection — a Session
    is not thread-safe to share, and a real contention test needs genuinely
    separate Postgres backends racing each other, not one connection
    pretending to be fifty."""
    db = SessionLocal()
    try:
        result = claim_slot(db, order_id, cook_duration_seconds=60)
        db.commit()
        return result is not None
    finally:
        db.close()


@pytest.mark.repeat(200)
def test_last_slot_has_exactly_one_winner(oven_with_one_free_slot: uuid.UUID) -> None:
    order_ids = [uuid.uuid4() for _ in range(50)]

    with ThreadPoolExecutor(max_workers=50) as pool:
        results = list(pool.map(_claim_in_its_own_session, order_ids))

    verify = SessionLocal()
    try:
        assert sum(results) == 1
        assert count_occupied_slots(verify) == 1
    finally:
        verify.close()


def test_claim_returns_none_when_the_oven_is_at_capacity(session: Session) -> None:
    _make_oven(session, slot_count=1)
    first = claim_slot(session, uuid.uuid4(), cook_duration_seconds=60)
    session.commit()
    assert first is not None

    second = claim_slot(session, uuid.uuid4(), cook_duration_seconds=60)
    session.commit()
    assert second is None


def test_claim_skips_slots_in_a_down_oven(session: Session) -> None:
    oven = Oven(name="Down Oven", slot_count=1, status="down")
    session.add(oven)
    session.flush()
    session.add(OvenSlot(oven_id=oven.id, slot_index=0))
    session.commit()

    result = claim_slot(session, uuid.uuid4(), cook_duration_seconds=60)
    assert result is None


def test_release_slot_frees_it_for_a_new_claim(session: Session) -> None:
    _make_oven(session, slot_count=1)
    claimed = claim_slot(session, uuid.uuid4(), cook_duration_seconds=60)
    session.commit()
    assert claimed is not None

    freed = release_slot(session, claimed.oven_slot_id)
    session.commit()
    assert freed.oven_id == claimed.oven_id

    reclaimed = claim_slot(session, uuid.uuid4(), cook_duration_seconds=60)
    session.commit()
    assert reclaimed is not None
    assert reclaimed.oven_slot_id == claimed.oven_slot_id


def test_reap_stuck_slots_reclaims_past_the_grace_period(session: Session) -> None:
    _make_oven(session, slot_count=1)
    claimed = claim_slot(session, uuid.uuid4(), cook_duration_seconds=60)
    session.commit()
    assert claimed is not None

    # Simulate a kitchen process that died mid-bake: back-date `frees_at`
    # well past now, as if the bake finished long ago and nothing released it.
    session.execute(
        text("UPDATE oven_slot SET frees_at = :past WHERE id = :id"),
        {"past": datetime.now(UTC) - timedelta(hours=1), "id": str(claimed.oven_slot_id)},
    )
    session.commit()

    freed = reap_stuck_slots(session, grace_seconds=30)
    session.commit()

    assert [f.oven_slot_id for f in freed] == [claimed.oven_slot_id]
    assert count_occupied_slots(session) == 0


def test_reap_is_idempotent_running_it_twice_changes_nothing(session: Session) -> None:
    _make_oven(session, slot_count=1)
    claimed = claim_slot(session, uuid.uuid4(), cook_duration_seconds=60)
    session.commit()
    assert claimed is not None
    session.execute(
        text("UPDATE oven_slot SET frees_at = :past WHERE id = :id"),
        {"past": datetime.now(UTC) - timedelta(hours=1), "id": str(claimed.oven_slot_id)},
    )
    session.commit()

    first_pass = reap_stuck_slots(session, grace_seconds=30)
    session.commit()
    second_pass = reap_stuck_slots(session, grace_seconds=30)
    session.commit()

    assert len(first_pass) == 1
    assert second_pass == []


def test_the_partial_unique_index_refuses_a_double_booking_even_from_a_bug(
    session: Session,
) -> None:
    """The second line of defence (DECISIONS.md §0002): even an application
    bug that bypasses `claim_slot` and writes two rows for one order cannot
    succeed — the database itself refuses."""
    oven_id = _make_oven(session, slot_count=2)
    order_id = uuid.uuid4()
    slots = session.query(OvenSlot).filter_by(oven_id=oven_id).order_by(OvenSlot.slot_index).all()

    slots[0].order_id = order_id
    session.commit()

    slots[1].order_id = order_id
    with pytest.raises(IntegrityError):
        session.commit()


@settings(
    suppress_health_check=[HealthCheck.function_scoped_fixture],
    deadline=None,
    max_examples=25,
)
@given(ops=st.lists(st.sampled_from(["claim", "release"]), min_size=1, max_size=40))
def test_occupied_slots_never_exceed_slot_count_under_any_interleaving(
    session: Session, ops: list[str]
) -> None:
    """Property test: across any interleaving of claims and releases, the
    invariant holds — occupied slots never exceed `slot_count`, and every
    successful claim is a genuinely free slot."""
    for table in ("oven_slot", "oven"):
        session.execute(text(f"TRUNCATE TABLE {table} CASCADE"))
    session.commit()

    slot_count = 3
    _make_oven(session, slot_count=slot_count)
    claimed_slot_ids: list[uuid.UUID] = []

    for op in ops:
        if op == "claim":
            result = claim_slot(session, uuid.uuid4(), cook_duration_seconds=60)
            session.commit()
            if result is not None:
                assert result.oven_slot_id not in claimed_slot_ids
                claimed_slot_ids.append(result.oven_slot_id)
        elif claimed_slot_ids:
            release_slot(session, claimed_slot_ids.pop())
            session.commit()

        assert count_occupied_slots(session) <= slot_count
