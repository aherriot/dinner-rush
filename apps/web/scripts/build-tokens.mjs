// Generates tokens.css, tokens.ts and tokens.storybook.ts from tokens.json.
// tokens.json is the only place a value is authored — DESIGN.md §9.1.
// Run via `pnpm tokens:build`. CI re-runs this and diffs the output — see
// the `tokens:check` script — so hand-editing a generated file cannot land.

import { readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

const designDir = fileURLToPath(new URL("../src/design/", import.meta.url));
const tokens = JSON.parse(readFileSync(designDir + "tokens.json", "utf-8"));

const HEADER =
  "/* GENERATED FILE — do not edit by hand.\n" +
  " * Source of truth: apps/web/src/design/tokens.json\n" +
  " * Regenerate with `pnpm tokens:build`. */\n\n";

// ---------------------------------------------------------------------------
// tokens.css
// ---------------------------------------------------------------------------

function themeBlock(theme) {
  const lines = [];
  for (const [name, value] of Object.entries(tokens.color)) {
    lines.push(`  --${name}: ${value[theme]};`);
  }
  return lines.join("\n");
}

function staticVarLines() {
  const lines = [];

  for (const [name, value] of Object.entries(tokens.space)) {
    lines.push(`  --${name}: ${value};`);
  }
  for (const [name, value] of Object.entries(tokens.radius)) {
    lines.push(`  --radius-${name === "default" ? "" : name}`.replace(/-$/, "") + `: ${value};`);
  }
  lines.push(`  --font-ui: ${tokens.typography.fontUi};`);
  lines.push(`  --font-mono: ${tokens.typography.fontMono};`);

  for (const [name, step] of Object.entries(tokens.typography.scale)) {
    const varName = /^metric/.test(name) ? name : `text-${name}`;
    lines.push(`  --${varName}-size: ${step.size};`);
    lines.push(`  --${varName}-line: ${step.line};`);
    lines.push(`  --${varName}-weight: ${step.weight};`);
  }

  for (const [name, value] of Object.entries(tokens.motion.duration)) {
    lines.push(`  --dur-${name}: ${value};`);
  }
  for (const [name, value] of Object.entries(tokens.motion.easing)) {
    lines.push(`  --ease-${name}: ${value};`);
  }

  return lines.join("\n");
}

function letterSpacingFor(name, sizePx) {
  if (name === "caption") return tokens.typography.letterSpacing.caption;
  if (sizePx >= 18) return tokens.typography.letterSpacing.tight;
  return tokens.typography.letterSpacing.normal;
}

function typographyUtilities() {
  const blocks = [];
  for (const [name, step] of Object.entries(tokens.typography.scale)) {
    const varName = /^metric/.test(name) ? name : `text-${name}`;
    const isMetric = /^metric/.test(name);
    const sizePx = Number.parseFloat(step.size);
    const tracking = letterSpacingFor(name, sizePx);
    blocks.push(
      `.${varName} {\n` +
        `  font-family: var(${isMetric ? "--font-mono" : "--font-ui"});\n` +
        `  font-size: var(--${varName}-size);\n` +
        `  line-height: var(--${varName}-line);\n` +
        `  font-weight: var(--${varName}-weight);\n` +
        `  letter-spacing: ${tracking};\n` +
        (isMetric ? `  font-variant-numeric: tabular-nums;\n` : "") +
        `}`,
    );
  }
  return blocks.join("\n\n");
}

const reducedMotionBlock = `@media (prefers-reduced-motion: reduce) {
  :root {
    --dur-instant: 0ms;
    --dur-fast: 0ms;
    --dur-normal: 0ms;
    --dur-slow: 0ms;
  }
}`;

const css =
  HEADER +
  `:root,\n[data-theme="dark"] {\n${themeBlock("dark")}\n\n${staticVarLines()}\n}\n\n` +
  `[data-theme="light"] {\n${themeBlock("light")}\n}\n\n` +
  `.metric,\ntable td,\n.timer,\n.counter {\n  font-variant-numeric: tabular-nums;\n}\n\n` +
  `${typographyUtilities()}\n\n` +
  `${reducedMotionBlock}\n`;

writeFileSync(designDir + "tokens.css", css);

// ---------------------------------------------------------------------------
// tokens.ts
// ---------------------------------------------------------------------------

const colorNames = Object.keys(tokens.color);
const spaceNames = Object.keys(tokens.space);
const radiusNames = Object.keys(tokens.radius).map((n) => (n === "default" ? "radius" : `radius-${n}`));
const durationNames = Object.keys(tokens.motion.duration).map((n) => `dur-${n}`);
const easingNames = Object.keys(tokens.motion.easing).map((n) => `ease-${n}`);
const typographyNames = Object.keys(tokens.typography.scale).map((n) =>
  /^metric/.test(n) ? n : `text-${n}`,
);

const statusOrder = Object.keys(tokens.statusMeta);

const ts =
  HEADER +
  `export type ColorToken =\n  | ${colorNames.map((n) => `"${n}"`).join("\n  | ")};\n\n` +
  `export type SpaceToken =\n  | ${spaceNames.map((n) => `"${n}"`).join("\n  | ")};\n\n` +
  `export type RadiusToken =\n  | ${radiusNames.map((n) => `"${n}"`).join("\n  | ")};\n\n` +
  `export type DurationToken =\n  | ${durationNames.map((n) => `"${n}"`).join("\n  | ")};\n\n` +
  `export type EasingToken =\n  | ${easingNames.map((n) => `"${n}"`).join("\n  | ")};\n\n` +
  `export type TypographyToken =\n  | ${typographyNames.map((n) => `"${n}"`).join("\n  | ")};\n\n` +
  `/** Renders any semantic token name as its \`var(--…)\` reference. Passing a\n` +
  ` * name outside the generated unions above is a compile error — that is the\n` +
  ` * enforcement mechanism, not a lint rule. */\n` +
  `export function cssVar(\n  name: ColorToken | SpaceToken | RadiusToken | DurationToken | EasingToken,\n): string {\n  return \`var(--\${name})\`;\n}\n\n` +
  `export type OrderStatus =\n  | ${statusOrder.map((n) => `"${n}"`).join("\n  | ")};\n\n` +
  `export interface StatusMeta {\n  glyph: string;\n  label: string;\n  motion: string | null;\n}\n\n` +
  `export const STATUS_META: Record<OrderStatus, StatusMeta> = ${JSON.stringify(tokens.statusMeta, null, 2)};\n\n` +
  `export const STATUS_ORDER: readonly OrderStatus[] = ${JSON.stringify(statusOrder)};\n`;

writeFileSync(designDir + "tokens.ts", ts);

// ---------------------------------------------------------------------------
// tokens.storybook.ts
// ---------------------------------------------------------------------------

function storybookTheme(theme) {
  const c = (name) => tokens.color[name][theme];
  return {
    base: theme,
    brandTitle: "Dinner Rush",
    brandUrl: "/",
    colorPrimary: c("accent"),
    colorSecondary: c("accent"),
    appBg: c("bg-base"),
    appContentBg: c("bg-panel"),
    appBorderColor: c("border-subtle"),
    appBorderRadius: Number.parseInt(tokens.radius.default, 10),
    textColor: c("text-primary"),
    textInverseColor: theme === "dark" ? c("text-primary") : c("text-primary"),
    barTextColor: c("text-secondary"),
    barSelectedColor: c("accent"),
    barBg: c("bg-panel"),
    inputBg: c("bg-inset"),
    inputBorder: c("border-strong"),
    inputTextColor: c("text-primary"),
    inputBorderRadius: Number.parseInt(tokens.radius.sm, 10),
    fontBase: tokens.typography.fontUi,
    fontCode: tokens.typography.fontMono,
  };
}

const storybookTs =
  HEADER +
  `import { create } from "storybook/theming";\n\n` +
  `const darkThemeVars = ${JSON.stringify(storybookTheme("dark"), null, 2)} as const;\n\n` +
  `const lightThemeVars = ${JSON.stringify(storybookTheme("light"), null, 2)} as const;\n\n` +
  `export const storybookThemeDark = create(darkThemeVars);\n` +
  `export const storybookThemeLight = create(lightThemeVars);\n`;

writeFileSync(designDir + "tokens.storybook.ts", storybookTs);

console.log("tokens:build wrote tokens.css, tokens.ts, tokens.storybook.ts");
