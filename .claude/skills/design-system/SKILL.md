---
name: design-system
description: Use whenever touching UI in this repo — building or editing anything under apps/web/src, adding a component, styling a screen, or reviewing frontend changes. Covers how to consume Dinner Rush's token system and component library, the enforcement it's under, and the specific mistakes that pass a casual glance but fail lint, axe, or visual regression.
---

# Dinner Rush design system

Authoritative spec: [DESIGN.md](../../docs/DESIGN.md). This skill is not a
restatement of it — it's the operational cheat sheet for actually building
against it without tripping the enforcement, written from the mistakes that
happened while building Phase 1.

**Read DESIGN.md §3–7 before styling anything.** If you're choosing a colour,
a size, or deciding whether to hand-build an interactive control, you've
skipped a section.

## The rule that matters most

Every UI change in this repo goes through the existing component library in
`apps/web/src/components/` and `apps/web/src/design/`. Before writing a new
component, check whether one already exists (`ls apps/web/src/components/`)
or whether Headless UI covers the interaction (§7 of DESIGN.md has the
mapping). Do not hand-roll a button, a dropdown, a modal, or a toggle.

## Do

- **Reference only semantic tokens** from `tokens.css` (`var(--status-baking)`,
  `var(--panel-gutter)`, `var(--radius)`, …). Never a hex/rgb/hsl literal,
  never a raw px in a spacing or colour property. The token list is in
  `apps/web/src/design/tokens.json` — if the value you need isn't there, it
  doesn't exist yet; don't invent one, ask.
- **Use `@headlessui/react` for anything interactive**: `Button`, `Dialog`,
  `Listbox`, `RadioGroup`, `Menu`, `Switch`, `Disclosure`, `Transition`. Style
  it by mapping its `data-*` state attributes (`data-hover`, `data-checked`,
  `data-open`, `data-disabled`, `data-focus-visible`) to tokens in a
  `Component.module.css`. This is not optional polish — it's where focus
  management, keyboard nav and ARIA wiring come from. See DESIGN.md §7 for
  which of the 13 existing components sit on which primitive.
- **Reset every interactive element with `all: unset; box-sizing: border-box;`
  as the first two lines**, then re-declare only what you need. Native
  `<button>`/`<select>` elements ship UA chrome (a light grey background in
  most browsers) that is *not* `transparent` by default — omitting a
  `background` declaration does not make one disappear. This exact bug shipped
  in the Ghost button variant and was only caught by an actual screenshot, not
  by lint or a unit test. If a component looks right in code but you haven't
  looked at a rendered screenshot, you haven't verified it.
- **Colocate every component** as `Component.tsx` + `Component.module.css` +
  `Component.stories.tsx` + `Component.test.tsx` inside its own directory
  under `apps/web/src/components/`. Every story needs its empty, loading and
  error states where applicable — those are mandatory, not nice-to-have.
- **Render components against `--bg-panel`, not `--bg-base`**, when checking
  contrast or building a story/demo harness. DESIGN.md §3 states every
  contrast ratio is measured against the panel background, not the page
  background — they differ slightly per theme and the gap is enough to fail
  WCAG AA on some status colours in light mode. The Storybook canvas decorator
  (`.storybook/preview.module.css`) is already set to `--bg-panel` for this
  reason; don't change it back to `--bg-base`.
- **Regenerate tokens after editing `tokens.json`**: `pnpm run tokens:build`
  (from `apps/web/`). Never hand-edit `tokens.css`, `tokens.ts`, or
  `tokens.storybook.ts` — they're generated and `tokens:check` fails CI on
  drift.
- **Run the full local check before calling UI work done**:
  ```bash
  cd apps/web
  pnpm run lint         # stylelint + eslint
  pnpm run test:unit    # vitest, jsdom
  pnpm run test:storybook  # every story as a test, axe included
  ```
  `pnpm run test:visual` (Playwright) is slow and CI-gated separately — run it
  locally only when you've changed something visual and need to update
  baselines (`pnpm run test:visual:update`), and know that **snapshots are
  OS-specific** (`-darwin.png` vs `-linux.png`). Baselines generated on macOS
  will not satisfy CI running on Linux. If you need to regenerate the Linux
  set locally, run it inside `mcr.microsoft.com/playwright:<version>-noble`
  via Docker with the repo mounted, matching whatever Playwright version is
  pinned in `apps/web/package.json`.

## Don't

- **Don't use the `border` / `border-color` / `border-radius` shorthand with a
  literal value that isn't a token.** stylelint's rule requires the *entire*
  declaration value to start with `var(--`. `border: 1px solid var(--x)` FAILS
  because the string starts with `1px`, not `var(--`. Reorder it:
  `border: var(--x) 1px solid;` — CSS doesn't care about shorthand order, the
  linter's regex does.
- **Don't declare `border-style` or `border-width` as standalone properties.**
  Both match stylelint's colour-property regex (anything starting with
  `border`) and neither has a token, so any literal value fails. Fold width
  and style into the reordered `border` shorthand instead.
- **Don't use bare CSS keywords in a restricted property** — `background:
  transparent`, `border: none`, `color: inherit` all fail the same rule
  (their value doesn't start with `var(--`). If you need "no border", omit the
  declaration entirely (the initial value already is none) rather than
  stating it.
- **Don't use the `background` shorthand with comma-separated layers where one
  layer is a bare colour** — `background: var(--x), linear-gradient(...)` is
  invalid CSS (colour isn't a per-layer value) and silently fails to render;
  it will pass stylelint and pass TypeScript and just not show up. Use
  space-separated single-layer shorthand instead: `background: var(--x)
  linear-gradient(...);`.
- **Don't add `anchor="..."` to a Headless UI `ListboxOptions` / `MenuItems`**
  if this component might ever be unit-tested with `@testing-library/react` —
  the anchor positioning pulls in floating-ui's `useFloating`, which calls
  `getComputedStyle` in a way jsdom cannot resolve and crashes the test with
  an opaque `font-sizes.js` error. Position the dropdown manually with
  `position: absolute` on a `position: relative` wrapper instead.
- **Don't forget `ResizeObserver` doesn't exist in jsdom.** If a test using a
  Headless UI `Listbox`/`Combobox` throws `ReferenceError: ResizeObserver is
  not defined`, it's not your component — check `vitest.setup.ts` has the
  no-op polyfill.
- **Don't give an ARIA `role` a required attribute conditionally.**
  `role="meter"` requires `aria-valuenow` on every render, including a
  disabled/unavailable state — `aria-valuenow={undefined}` still trips axe's
  `aria-required-attr` rule. If there's no numeric value to report (e.g. an
  oven that's `down`), don't use `role="meter"` for that state at all; switch
  to `role="img"` with a descriptive `aria-label`.
- **Don't skip the screenshot.** Lint, typecheck and unit tests all passed on
  the Ghost button while it rendered with a UA-grey background and washed-out
  text — none of those tools render CSS. For any non-trivial visual change,
  actually look at it (Storybook dev server + a screenshot, or the Playwright
  report) before considering the work done.

## Where to look

| Question | Answer |
| --- | --- |
| What token exists for X? | `apps/web/src/design/tokens.json` |
| Is there already a component for this? | `ls apps/web/src/components/` |
| What's the exact hex/ratio for a status? | DESIGN.md §3.3 |
| Which Headless UI primitive backs which component? | DESIGN.md §7 |
| What stylelint/eslint rules are actually enforced? | DESIGN.md §9.3, `apps/web/.stylelintrc.json`, `apps/web/eslint.config.js` |
| Board layout grid | DESIGN.md §10 |
