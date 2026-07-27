# Design direction

This is an operations console, not a consumer app. That single sentence is the
argument; everything else in [DESIGN.md](../DESIGN.md) is its consequence.

## The reference points

Air traffic control. Trading terminals. Mission control. Not food delivery
apps — that comparison is the positioning problem this project has to solve,
and the visual language is how it gets solved without saying so. A screen
that looks like a consumer ordering app invites the "food delivery app"
comparison on sight, before a single sentence of README is read. A screen
that looks like instrumentation invites a different question — "what is this
system doing under load" — which is the actual pitch.

## What that means, concretely

**Dense over airy.** The board is read at a glance by someone whose hands are
full — cooking, dispatching, watching a rush unfold. Marketing-page whitespace
is wasted signal here; it pushes information off-screen for no return. Rows
are 28px, panels touch at 8px gaps, and nothing breathes just because
breathing looks considered.

**Dark by default.** It's a wall display in a kitchen — high-contrast dark
surfaces hold up under mixed kitchen lighting and don't blind anyone standing
near it at night. Light theme is fully built and fully supported (the
storefront defaults to it), but dark is the case every other decision is
optimised for.

**Numbers are typographic objects, not incidental text.** Tabular figures
everywhere a value changes — queue depth, wait time, courier ETA. A counter
ticking from 9 to 10 must not shift a single pixel of layout around it. This
is a small technical decision (`font-variant-numeric: tabular-nums`) that
reads, cumulatively, as the difference between a dashboard and a toy.

**Colour carries meaning, never decoration.** Every hue in the palette is
assigned to exactly one domain state and nothing is added for warmth. The
sharpest example: `rejected` is violet, not red, because a kitchen at
capacity refusing an order is the system working correctly — backpressure,
not failure — and colour is the fastest channel available to say so before a
viewer reads a single label. See DESIGN.md §2.

**Motion is information, not polish.** A slot filling, a counter
incrementing, a rejection landing — three sanctioned animations, driven by
real state change, nothing else. A board repainting continuously cannot
afford decorative easing; every animation frame that isn't carrying a state
change is a frame competing with one that is.

**Borders, not shadows.** Elevation on near-black surfaces reads as 1px
borders and background-level steps (`--bg-panel` → `--bg-raised`). Drop
shadows on dark backgrounds render as smudges, not depth — they're a light-
theme trick that doesn't survive the trip to dark.

## What is explicitly rejected

Rounded-friendly SaaS styling. Gradient fills. Illustration. Glassmorphism.
Generous radii — 8px is the ceiling for anything that isn't a pill-shaped
status badge. Hero whitespace. Decorative iconography. Any typeface with
personality above 16px. Every one of these is a legitimate choice for a
consumer product and a wrong one here — they all soften a screen whose entire
job is to read as precise under load.

## The one thing to defend out loud

`rejected` is violet. It is the single design decision in this system that
carries an argument rather than a preference, and it is covered in full in
DESIGN.md §2 — read that section before touching the status colour table.
