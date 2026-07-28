"""Dinner Rush's simulator — an ordinary API client (CLAUDE.md §5).

It authenticates via `POST /auth/token` with seeded credentials, holds no
service or database credentials, and imports nothing from `services/gateway`
or `services/kitchen`. Poisson customer arrivals against the real public API;
courier behaviour lands in Phase 7 once dispatch exists to call.
"""
