"""The deterministic failure this spike exists to show (DECISIONS.md §0002):
claim with `SET NX EX 1`, sleep past the TTL to simulate a stalled process,
let a second claimer succeed, assert two orders occupy a one-slot oven.

No timing race to get unlucky on — sleeping past a 1-second TTL always
expires it, so this fails the naive design every single run, not
occasionally.
"""

import os
import time
import uuid
from collections.abc import Iterator

import pytest
import redis

from redis_lease_allocation import claim_slot_via_lease


@pytest.fixture
def client() -> Iterator[redis.Redis]:
    conn = redis.Redis.from_url(os.environ.get("REDIS_URL", "redis://localhost:6379/0"))
    yield conn
    conn.close()


def test_a_stalled_holder_and_a_new_claimer_both_believe_they_own_the_slot(
    client: redis.Redis,
) -> None:
    slot_key = f"spike:oven-slot:{uuid.uuid4()}"
    order_a, order_b = "order-a", "order-b"

    acquired_by_a = claim_slot_via_lease(client, slot_key, order_a, ttl_seconds=1)
    assert acquired_by_a is True  # order A believes it now owns the one slot

    # order A is "baking" — a GC pause, a slow query, or a bake that runs
    # longer than the TTL. It never releases the lease itself; the lease
    # just expires out from under it while A is still very much alive.
    time.sleep(1.2)

    acquired_by_b = claim_slot_via_lease(client, slot_key, order_b, ttl_seconds=1)

    # The failure: a second, completely legitimate claim succeeds on the
    # exact same slot while the first holder still believes it holds it.
    # Contrast with `kitchen.slots.claim_slot` (DECISIONS.md §0002), where
    # occupancy is a committed row and a partial unique index makes this
    # scenario impossible to even attempt — there is no lease to expire.
    assert acquired_by_b is True

    client.delete(slot_key)
