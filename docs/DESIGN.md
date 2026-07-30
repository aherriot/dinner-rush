# Dinner Rush — design system

The authoritative token values. Phase 1 of [PHASES.md](PHASES.md) builds this;
every surface after it consumes it. **No component may author a colour, a size,
or a duration.** Everything below is generated from `tokens.json` into
`tokens.css` (custom properties) and `tokens.ts` (typed literals).

---

## 1. Direction

**This is an operations console, not a consumer app.** The reference points are
air traffic control, trading terminals and mission control — not food delivery
apps, which is the entire positioning problem this project has to solve.

What that means in practice:

- **Dense over airy.** This screen is read at a glance by someone with their
  hands full. Whitespace that would be elegant in a marketing page is wasted
  signal here.
- **Dark by default.** It is a wall display in a kitchen. Light theme exists and
  is fully supported, but dark is the designed-for case.
- **Numbers are typographic objects.** Tabular figures everywhere. A queue depth
  ticking 9 → 10 must not shift the layout by a pixel.
- **Colour carries meaning, never decoration.** Every hue in the palette is
  assigned to a domain state. There are no "brand accents" applied for warmth.
- **Motion is information.** A slot filling, a counter incrementing, a rejection
  landing. Nothing eases, fades or slides because it looked nice.
- **Borders, not shadows.** Elevation on dark surfaces reads as 1px borders and
  background steps. Drop shadows on near-black look like smudges.

**Explicitly rejected:** rounded-friendly SaaS styling, gradient fills,
illustration, glassmorphism, generous radii, hero whitespace, decorative
iconography, and any typeface with personality above 16px.

---

## 2. The decision that expresses the thesis

**`rejected` is not red.**

A restaurant at capacity refusing an order is the system working *correctly* —
it is backpressure, the single most valuable behaviour this project
demonstrates. `failed` (courier dropped it, nobody answered the door) is a
genuine error. Encoding both in red would say they are the same kind of event,
and they are not.

So `rejected` is **violet** — high-visibility, unmistakably deliberate, visually
adjacent to nothing else in the palette. `failed` is red. On the board during a
Friday rush you can see the violet band appear at the door while the reds stay
flat, and that picture *is* the pitch.

This is the one thing in the design system to defend out loud in an interview.

---

## 3. Colour

All values verified against WCAG 2.1. Ratios are measured against the panel
background of their theme (`#131720` dark, `#FFFFFF` light). **Every token below
clears 4.5:1**, so any of them may carry text.

### 3.1 Surfaces and structure

| Token | Dark | Light | Use |
| --- | --- | --- | --- |
| `--bg-base` | `#0B0E14` | `#F4F6FA` | Page background |
| `--bg-panel` | `#131720` | `#FFFFFF` | Panel/card surface |
| `--bg-raised` | `#1A2029` | `#FFFFFF` | Hover rows, popovers, raised controls |
| `--bg-inset` | `#080A0F` | `#EAEEF5` | Wells, inputs, empty oven slots |
| `--border-subtle` | `#232A36` | `#E2E7F0` | Row dividers, panel gutters |
| `--border-strong` | `#2E3644` | `#C8D0DE` | Panel edges, input borders |
| `--border-focus` | `#FF8A3D` | `#B04E0C` | Focus ring (2px, 2px offset) |

### 3.2 Text

| Token | Dark | ratio | Light | ratio | Use |
| --- | --- | --- | --- | --- | --- |
| `--text-primary` | `#E6EAF2` | 14.87 | `#0E1420` | 18.43 | Body, values, headings |
| `--text-secondary` | `#9BA6B8` | 7.29 | `#4A5568` | 7.53 | Labels, column headers |
| `--text-tertiary` | `#7A8494` | 4.74 | `#6B7688` | 4.59 | Timestamps, hints, units |

### 3.3 Order status — the core of the system

One row per state in the lifecycle. Every surface that renders an order state
reads this table and nothing else.

| State | Token | Dark | ratio | Light | ratio | Shape | Motion |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `placed` | `--status-placed` | `#8B98AE` | 6.15 | `#5A6880` | 5.64 | ○ hollow dot | enter 140ms |
| `accepted` | `--status-accepted` | `#4C9AFF` | 6.30 | `#1B6BD6` | 5.10 | ● dot | — |
| `queued` | `--status-queued` | `#D9A441` | 7.97 | `#9A6B10` | 4.68 | ▢ hollow square | — |
| `prepping` | `--status-prepping` | `#F0873C` | 7.03 | `#B85A12` | 4.66 | ◐ half | — |
| `baking` | `--status-baking` | `#FF6B35` | 6.32 | `#D14808` | 4.52 | ◕ three-quarter | progress fill |
| `boxed` | `--status-boxed` | `#FFB03A` | 9.84 | `#96650A` | 5.04 | ▣ filled square | — |
| `ready` | `--status-ready` | `#3DD68C` | 9.56 | `#0B7A4B` | 5.39 | ★ star | **pulse 1.2s ×3** |
| `assigned` | `--status-assigned` | `#4FC3F7` | 8.95 | `#0C7BB5` | 4.65 | ◇ hollow diamond | — |
| `picked_up` | `--status-picked-up` | `#29B6F6` | 7.78 | `#0A6E9E` | 5.62 | ◆ diamond | — |
| `delivering` | `--status-delivering` | `#2AA3E0` | 6.33 | `#08608A` | 6.88 | ▸ chevron | — |
| `delivered` | `--status-delivered` | `#5FA97F` | 6.38 | `#3D7A57` | 5.10 | ✓ check | recede 220ms |
| `rejected` | `--status-rejected` | `#B47CE6` | 5.95 | `#7B3FB8` | 6.47 | ⊘ slash-circle | **enter 80ms, no ease** |
| `failed` | `--status-failed` | `#F2545B` | 5.29 | `#C41E3A` | 5.84 | ✕ cross | — |

`late` is a **modifier, not a state** — an order can be `baking` and late. It
renders as a 2px left border in `--status-late` (`#FFB03A` dark / `#96650A`
light) plus the label suffix `· LATE`. Never recolour the underlying state.

**Shape is not optional.** Status is never encoded by colour alone — the glyph
and the text label both carry it independently. That is what makes the board
readable to a colourblind viewer and what makes the accessibility claim true
rather than aspirational.

### 3.4 Resource states

| Token | Dark | Light | Use |
| --- | --- | --- | --- |
| `--oven-free` | `#2E3644` | `#C8D0DE` | Empty slot |
| `--oven-reserved` | `#D9A441` | `#9A6B10` | Claimed, not yet loaded |
| `--oven-occupied` | `#FF6B35` | `#D14808` | Baking |
| `--oven-down` | `#F2545B` | `#C41E3A` | Out of service — 45° hatch, 4px pitch |
| `--courier-idle` | `#78828F` | `#7B8496` | Online, unassigned |
| `--courier-active` | `#4FC3F7` | `#0C7BB5` | On a trip |
| `--courier-offline` | `#78828F` | `#7B8496` | Offline — 40% opacity + dashed stroke |
| `--service-healthy` | `#3DD68C` | `#0B7A4B` | `SystemMap` node — answering normally |
| `--service-degraded` | `#D9A441` | `#9A6B10` | `SystemMap` node — reachable but reconnecting/at capacity |
| `--service-down` | `#F2545B` | `#C41E3A` | `SystemMap` node — unreachable |
| `--service-unknown` | `#7A8494` | `#6B7688` | `SystemMap` node — no independent signal (e.g. a service's own Postgres) |

### 3.5 Accent

| Token | Dark | ratio | Light | ratio |
| --- | --- | --- | --- | --- |
| `--accent` | `#FF8A3D` | 7.65 | `#B04E0C` | 5.33 |
| `--accent-hover` | `#FFA05C` | — | `#C25A10` | — |
| `--accent-active` | `#E5762B` | — | `#9A430A` | — |

Amber-orange, because it is oven heat and because it is not the blue-violet that
every developer tool defaults to. Reserved for: primary actions, the focus ring,
the active speed selector, and the wordmark. **Never for status.**

---

## 4. Typography

| Token | Family |
| --- | --- |
| `--font-ui` | `Inter var`, system-ui, sans-serif |
| `--font-mono` | `JetBrains Mono`, ui-monospace, monospace |

Both self-hosted via npm — no CDN, no network dependency, consistent with the
project running fully offline.

**All numerics use tabular figures.** On `--font-ui` that means
`font-variant-numeric: tabular-nums`, applied globally to `.metric`, table
cells, timers and counters. This is non-negotiable: a board where digits shift
width as they tick looks broken at a glance.

| Token | Size | Line | Weight | Use |
| --- | --- | --- | --- | --- |
| `--text-caption` | 11px | 1.35 | 500 | Column headers, units, axis labels |
| `--text-sm` | 12px | 1.40 | 400 | Dense table rows — the board default |
| `--text-body` | 13px | 1.45 | 400 | Forms, storefront body |
| `--text-lg` | 15px | 1.45 | 400 | Storefront emphasis |
| `--text-h3` | 18px | 1.30 | 600 | Panel titles |
| `--text-h2` | 24px | 1.25 | 600 | Page titles |
| `--text-h1` | 32px | 1.20 | 700 | Storefront hero only |
| `--metric-sm` | 20px | 1.10 | 600 mono | Inline metrics |
| `--metric` | 28px | 1.05 | 600 mono | Panel metrics |
| `--metric-lg` | 40px | 1.00 | 700 mono | Status bar headline figures |

Order codes, IDs, timers, coordinates and all metric values render in
`--font-mono`. Prose and labels never do.

Letter-spacing: `-0.01em` above 18px, `0.02em` on `--text-caption` uppercase
labels, `0` elsewhere.

---

## 5. Space, size, radius

4px base unit. Nothing off-scale.

```
--space-0   0     --space-4   8px    --space-8   24px
--space-1   2px   --space-5   12px   --space-9   32px
--space-2   4px   --space-6   16px   --space-10  48px
--space-3   6px   --space-7   20px   --space-11  64px
```

| Token | Value | Use |
| --- | --- | --- |
| `--row-dense` | 28px | Board tables |
| `--row-default` | 32px | Storefront tables |
| `--control-sm` / `--control` | 24px / 32px | Buttons, inputs |
| `--panel-gutter` | 12px | Panel inner padding |
| `--panel-gap` | 8px | Gap between board panels |

Radius stays small — this is instrumentation, not a consumer app.

```
--radius-sm 2px   --radius 4px   --radius-lg 6px   --radius-pill 999px
```

`--radius-pill` is for StatusPill only. **8px is the ceiling for everything
else** and there is no reason to reach it.

---

## 6. Motion

```
--dur-instant  80ms    --ease-out    cubic-bezier(0.16, 1, 0.3, 1)
--dur-fast    140ms    --ease-inout  cubic-bezier(0.65, 0, 0.35, 1)
--dur-normal  220ms
--dur-slow    400ms
```

**The rule:** motion is permitted only when it communicates a state change or a
value change. Entrances, hovers and decorative transitions are not motion, they
are noise, and on a board repainting at 10 Hz they are actively harmful.

Three sanctioned animations, and no others without an ADR:

1. **Slot fill** — oven slot progress, linear, driven by real bake progress
2. **Ready pulse** — `--status-ready` opacity 1 → 0.55 → 1, 1.2s, exactly three
   cycles then stop. It is a call to action, not an ambient loop
3. **Row enter/exit** — 140ms opacity + 4px translate on the order feed

`@media (prefers-reduced-motion: reduce)` collapses every duration to 0ms except
the slot fill, which becomes a stepped update. This is a media query in
`tokens.css`, not a per-component concern.

---

## 7. Components

Built in Phase 1, in Storybook, before any screen exists.

**Headless UI first.** Anywhere a component needs focus management, keyboard
navigation or ARIA state, reach for `@headlessui/react` before writing it by
hand — it ships zero styling, so it costs nothing against the token-purity
rule in §9, and it removes an entire class of bugs (focus traps, roving
tabindex, escape-to-close) from the surface we're responsible for. Our code
is limited to: composing the primitive, mapping its `data-*` state attributes
(`data-hover`, `data-checked`, `data-open`, …) to semantic tokens, and adding
the domain content. What's left as hand-built is exactly the set Headless UI
doesn't attempt: data visualisation and dense-data rendering.

| Component | Built on | States that must be in Storybook |
| --- | --- | --- |
| `Button` | Headless UI `Button` | primary, secondary, ghost, danger × default/hover/active/focus/disabled/loading |
| `StatusPill` | custom — domain visual, no Headless UI equivalent | all 13 order states, plus each with the `late` modifier |
| `Panel` | custom layout; wraps Headless UI `Disclosure` when collapsible | with/without title, with toolbar, loading, empty, error |
| `DataTable` | custom — Headless UI has no table primitive | dense/default, sorted, empty, loading skeleton, 500-row virtualised |
| `Meter` | custom — data visualisation | 0/25/50/100%, at-capacity, over-capacity, down |
| `Sparkline` | custom — SVG data visualisation | flat, rising, falling, single point, no data |
| `MetricTile` | custom — token + typography composition | value, value + delta, no data, stale |
| `Toolbar` | composes Headless UI `RadioGroup` (segmented control, e.g. speed) and `Menu` (overflow actions, e.g. chaos scenarios) | segmented control, toggle group, disabled |
| `Select` | Headless UI `Listbox` — admin controls: oven status, menu availability | default, open, disabled, error |
| `Modal` | Headless UI `Dialog` (built-in enter/exit transition) | confirm, destructive-confirm |
| `Toast` | custom — no Headless UI equivalent; uses Headless UI `Transition` for enter/exit only | info, success, warning, error, stacked ×3 |
| `OvenSlot` | custom — domain visualisation | free, reserved, occupied 0–100%, down |
| `CourierDot` | custom — domain visualisation | idle, active, offline, selected |

**Empty, loading and error states are mandatory for every component.** They are
where portfolio UIs are exposed, and they are the states a live board spends
real time in.

The Headless UI dependency does not relax §9: a `Component.module.css` styling
a Headless UI primitive is still bound by the semantic-tokens-only rule, and
state selectors like `&[data-checked]` take a token the same way `:hover`
would.

---

## 8. Identity

The wordmark is `DINNER RUSH` in `--font-ui` 600, `0.08em` tracking, uppercase,
`--text-primary` with the second word in `--accent`. Favicon is a filled square
in `--oven-occupied` on `--bg-base`. Both live in the design package and are
imported, never redrawn. A demo screen with a hand-placed logo reads as
unfinished in exactly the frame where polish is being judged.

---

## 9. Enforcement

The tokens are not the deliverable. **The enforcement is the deliverable** —
anyone can write a colour variables file, and the gap between that and a
machine-checked system is the entire signal.

### 9.1 Token pipeline

```
src/design/tokens.json          ← the only place a value is authored
        │ pnpm tokens:build
        ├── tokens.css          ← :root + [data-theme] custom properties
        ├── tokens.ts           ← typed literals, exported unions
        └── tokens.storybook.ts ← Storybook theme
```

`tokens:build` runs in CI and fails if the generated files differ from what is
committed. Editing `tokens.css` by hand is therefore impossible to land.

### 9.2 Two layers, strictly separated

**Primitive** tokens (`--orange-500`, `--space-6`) exist only inside
`tokens.json`. **A component may reference only semantic tokens**
(`--status-baking`, `--panel-gutter`). This is what makes a re-theme a one-file
change, and it is the thing most design systems get wrong.

### 9.3 Lint rules that fail CI

```jsonc
// .stylelintrc.json
{
  "rules": {
    "color-no-hex": true,
    "declaration-property-value-disallowed-list": {
      "/^(color|background|background-color|border|fill|stroke)/":
        ["/^(?!var\\(--)/"],
      "/^(margin|padding|gap|top|right|bottom|left)/":
        ["/^-?\\d+(px|rem|em)$/"]
    },
    "custom-property-pattern":
      "^(?!.*-(50|100|200|300|400|500|600|700|800|900)$).*$"
  }
}
```

That last rule is the important one: it rejects any *primitive* token name
appearing in component CSS, enforcing the layer separation from §9.2.

ESLint bans inline colour props and raw `style={{ color: … }}`. `tokens.ts`
exports string-literal unions, so an invalid token name is a **compile error**,
not a silent fallback.

### 9.4 Automated checks

| Check | Gate |
| --- | --- |
| `tokens:build` diff | CI fails if generated files are stale |
| stylelint + eslint | CI fails on any raw hex, rgb, or off-scale px |
| `tsc --noEmit` | invalid token names are type errors |
| Playwright visual regression | every Storybook story, light + dark |
| Contrast assertion | every text/background pair in `tokens.json` ≥ 4.5:1 |
| Axe | zero violations on both surfaces |

The contrast check is a unit test over `tokens.json`, not a manual audit — the
numbers in §3 were produced by it. Adding a token that fails is a red build.

### 9.5 The rule an agent must not break

> A component file containing `#`, `rgb(`, `hsl(`, or a raw pixel value in a
> spacing or colour property is a defect, regardless of how it looks.

---

## 10. Layout — the board

```
┌─────────────┬──────────────────────────┬────────────────┐
│ ORDER FEED  │ KITCHEN                  │ DISPATCH       │
│ 340px       │ 1fr                      │ 380px          │
├─────────────┴──────────────────────────┴────────────────┤
│ STATUS BAR — clock · speed · rate · p95 · chaos    56px │
└─────────────────────────────────────────────────────────┘
```

`grid-template-columns: 340px 1fr 380px`, `grid-template-rows: 1fr 56px`,
`gap: var(--panel-gap)`. Designed for 1440×900 and must remain legible when
projected. Below 1100px the three panels stack and the status bar becomes
sticky — the board is not a mobile surface and should not pretend to be.

Order feed widened from its original 280px to fit a third column (placed-ago
time, alongside order code and status) and the per-order drill-in it opens.

The storefront is a separate, deliberately calmer layout: single column, max
`720px`, `--text-body`, light theme default. It uses the same tokens and the
same components. **That contrast is itself a demonstration** — one system, two
registers, no drift.
