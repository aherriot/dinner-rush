"""Deterministic simulated-customer identities.

Must match front-of-house's `manage.py seed` exactly (`SIMULATOR_EMAIL_FORMAT`
there) — the simulator never creates its own customers, since there is no
signup flow to use (ADR 0002 §2) and it holds no database credentials to
create one directly (CLAUDE.md §5) even if there were.
"""

_EMAIL_FORMAT = "sim{n:04d}@example.com"


def customer_email(n: int) -> str:
    return _EMAIL_FORMAT.format(n=n)
