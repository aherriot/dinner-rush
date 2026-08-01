# web

React + TypeScript + Vite. Three screens on top of the Phase 1 design system:
the **Storefront** and **order tracker** (Phase 2/3) and the **ops board**
(Phase 8) — order feed, kitchen panel, dispatch map and system map, live over
websockets with speed control and chaos buttons.

```bash
pnpm dev                # app shell — storefront, tracker and /board
pnpm storybook          # design system, http://localhost:6006

pnpm run tokens:build   # regenerate tokens.css/tokens.ts from tokens.json
pnpm run api:generate   # regenerate src/api/schema.ts from front-of-house's OpenAPI
pnpm run lint           # stylelint + eslint
pnpm run test:unit      # vitest (jsdom)
pnpm run test:storybook # every story as a test, with axe checks
pnpm run test:visual    # Playwright visual regression, light + dark
```

CI checks that `tokens:build` and `api:generate` are up to date and fails the
build on drift — see `pnpm run tokens:check` / `api:check`.

See [docs/DESIGN.md](../../docs/DESIGN.md) for the token system and component
inventory, and [docs/design/direction.md](../../docs/design/direction.md) for
the design argument behind it.
