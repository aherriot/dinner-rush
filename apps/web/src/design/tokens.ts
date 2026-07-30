/* GENERATED FILE — do not edit by hand.
 * Source of truth: apps/web/src/design/tokens.json
 * Regenerate with `pnpm tokens:build`. */

export type ColorToken =
  | "bg-base"
  | "bg-panel"
  | "bg-raised"
  | "bg-inset"
  | "border-subtle"
  | "border-strong"
  | "border-focus"
  | "text-primary"
  | "text-secondary"
  | "text-tertiary"
  | "status-placed"
  | "status-accepted"
  | "status-queued"
  | "status-prepping"
  | "status-baking"
  | "status-boxed"
  | "status-ready"
  | "status-assigned"
  | "status-picked-up"
  | "status-delivering"
  | "status-delivered"
  | "status-rejected"
  | "status-failed"
  | "status-late"
  | "oven-free"
  | "oven-reserved"
  | "oven-occupied"
  | "oven-down"
  | "courier-idle"
  | "courier-active"
  | "courier-offline"
  | "service-healthy"
  | "service-degraded"
  | "service-down"
  | "service-unknown"
  | "accent"
  | "accent-hover"
  | "accent-active";

export type SpaceToken =
  | "row-dense"
  | "row-default"
  | "control-sm"
  | "control"
  | "panel-gutter"
  | "panel-gap";

export type RadiusToken =
  | "radius-sm"
  | "radius"
  | "radius-lg"
  | "radius-pill";

export type DurationToken =
  | "dur-instant"
  | "dur-fast"
  | "dur-normal"
  | "dur-slow";

export type EasingToken =
  | "ease-out"
  | "ease-inout";

export type TypographyToken =
  | "text-caption"
  | "text-sm"
  | "text-body"
  | "text-lg"
  | "text-h3"
  | "text-h2"
  | "text-h1"
  | "metric-sm"
  | "metric"
  | "metric-lg";

/** Renders any semantic token name as its `var(--…)` reference. Passing a
 * name outside the generated unions above is a compile error — that is the
 * enforcement mechanism, not a lint rule. */
export function cssVar(
  name: ColorToken | SpaceToken | RadiusToken | DurationToken | EasingToken,
): string {
  return `var(--${name})`;
}

export type OrderStatus =
  | "placed"
  | "accepted"
  | "queued"
  | "prepping"
  | "baking"
  | "boxed"
  | "ready"
  | "assigned"
  | "picked_up"
  | "delivering"
  | "delivered"
  | "rejected"
  | "failed";

export interface StatusMeta {
  glyph: string;
  label: string;
  motion: string | null;
}

export const STATUS_META: Record<OrderStatus, StatusMeta> = {
  "placed": {
    "glyph": "○",
    "label": "Placed",
    "motion": "enter 140ms"
  },
  "accepted": {
    "glyph": "●",
    "label": "Accepted",
    "motion": null
  },
  "queued": {
    "glyph": "▢",
    "label": "Queued",
    "motion": null
  },
  "prepping": {
    "glyph": "◐",
    "label": "Prepping",
    "motion": null
  },
  "baking": {
    "glyph": "◕",
    "label": "Baking",
    "motion": "progress fill"
  },
  "boxed": {
    "glyph": "▣",
    "label": "Boxed",
    "motion": null
  },
  "ready": {
    "glyph": "★",
    "label": "Ready",
    "motion": "pulse 1.2s ×3"
  },
  "assigned": {
    "glyph": "◇",
    "label": "Assigned",
    "motion": null
  },
  "picked_up": {
    "glyph": "◆",
    "label": "Picked up",
    "motion": null
  },
  "delivering": {
    "glyph": "▸",
    "label": "Delivering",
    "motion": null
  },
  "delivered": {
    "glyph": "✓",
    "label": "Delivered",
    "motion": "recede 220ms"
  },
  "rejected": {
    "glyph": "⊘",
    "label": "Rejected",
    "motion": "enter 80ms, no ease"
  },
  "failed": {
    "glyph": "✕",
    "label": "Failed",
    "motion": null
  }
};

export const STATUS_ORDER: readonly OrderStatus[] = ["placed","accepted","queued","prepping","baking","boxed","ready","assigned","picked_up","delivering","delivered","rejected","failed"];
