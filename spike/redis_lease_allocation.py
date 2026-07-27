"""The naive approach DECISIONS.md §0002 rejects: a Redis lease
(`SET NX EX`) as the source of truth for oven-slot occupancy, instead of a
committed Postgres row.

Not used anywhere in the real system (see `services/kitchen/src/kitchen/slots.py`
for what shipped instead) — kept only on this branch to demonstrate the
failure mode that design avoids. See `spike/README.md`.
"""

import redis


def claim_slot_via_lease(
    client: redis.Redis, slot_key: str, holder_id: str, ttl_seconds: int
) -> bool:
    """Returns True if `holder_id` acquired the lease."""
    return bool(client.set(slot_key, holder_id, nx=True, ex=ttl_seconds))


def release_lease(client: redis.Redis, slot_key: str, holder_id: str) -> None:
    current = client.get(slot_key)
    if current is not None and current.decode() == holder_id:
        client.delete(slot_key)
