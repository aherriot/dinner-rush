# Dinner Rush

A simulated pizza operation running under real load — see
[docs/PIZZA.md](docs/PIZZA.md) for the pitch and [CLAUDE.md](CLAUDE.md) for
the standing rules this repo is built against.

Built in phases; see [docs/PHASES.md](docs/PHASES.md). Currently at
**Phase 1 — Design system**.

## Quickstart

```bash
make up      # bring the stack up; every container healthy in <90s
make lint    # ruff, mypy strict
make test    # pytest against real Postgres + Redis
make down
```

`gateway` serves on `http://localhost:8000` — `/healthz` for liveness,
`/readyz` for real dependency checks (Postgres, Redis).

```bash
cd apps/web
pnpm storybook   # design system — tokens, primitives, DINNER RUSH wordmark
```

See [apps/web/README.md](apps/web/README.md) for the frontend command surface
(lint, tests, visual regression) and [docs/DESIGN.md](docs/DESIGN.md) for the
token system itself.

## Layout

See CLAUDE.md §3 for the full repo layout and the reasoning behind it.

## Decisions

- [docs/adr/0001-why-three-services.md](docs/adr/0001-why-three-services.md)

More ADRs land as later phases make more decisions worth recording.
