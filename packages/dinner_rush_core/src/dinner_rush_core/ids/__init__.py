"""UUIDv7 generation (RFC 9562).

Every domain id in SPEC.md §1 is a UUIDv7 — time-ordered, so primary key
indexes stay append-friendly under load. The stdlib doesn't ship `uuid.uuid7`
on Python 3.13, so this is the one shared implementation every service's
models use.
"""

import os
import time
import uuid


def uuid7() -> uuid.UUID:
    unix_ts_ms = time.time_ns() // 1_000_000
    rand = int.from_bytes(os.urandom(10), byteorder="big")
    rand_a = (rand >> 62) & 0x0FFF  # 12 bits
    rand_b = rand & 0x3FFF_FFFF_FFFF_FFFF  # 62 bits

    value = unix_ts_ms << 80
    value |= 0x7 << 76  # version 7
    value |= rand_a << 64
    value |= 0b10 << 62  # variant
    value |= rand_b

    return uuid.UUID(int=value)
