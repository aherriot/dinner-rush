# web

React + TypeScript + Vite. The design system lives in Storybook — no screens
exist yet, see [PHASES.md](../../docs/PHASES.md) Phase 2 and Phase 8.

```bash
pnpm storybook          # design system, http://localhost:6006
pnpm dev                # app shell (placeholder until Phase 2)
pnpm run tokens:build   # regenerate tokens.css/tokens.ts from tokens.json
pnpm run lint           # stylelint + eslint
pnpm run test:unit      # vitest (jsdom)
pnpm run test:storybook # every story as a test, with axe checks
pnpm run test:visual    # Playwright visual regression, light + dark
```

See [docs/DESIGN.md](../../docs/DESIGN.md) for the token system and component
inventory, and [docs/design/direction.md](../../docs/design/direction.md) for
the design argument behind it.
