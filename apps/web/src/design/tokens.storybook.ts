/* GENERATED FILE — do not edit by hand.
 * Source of truth: apps/web/src/design/tokens.json
 * Regenerate with `pnpm tokens:build`. */

import { create } from "storybook/theming";

const darkThemeVars = {
  "base": "dark",
  "brandTitle": "Dinner Rush",
  "brandUrl": "/",
  "colorPrimary": "#FF8A3D",
  "colorSecondary": "#FF8A3D",
  "appBg": "#0B0E14",
  "appContentBg": "#131720",
  "appBorderColor": "#232A36",
  "appBorderRadius": 4,
  "textColor": "#E6EAF2",
  "textInverseColor": "#E6EAF2",
  "barTextColor": "#9BA6B8",
  "barSelectedColor": "#FF8A3D",
  "barBg": "#131720",
  "inputBg": "#080A0F",
  "inputBorder": "#2E3644",
  "inputTextColor": "#E6EAF2",
  "inputBorderRadius": 2,
  "fontBase": "'Inter var', system-ui, sans-serif",
  "fontCode": "'JetBrains Mono', ui-monospace, monospace"
} as const;

const lightThemeVars = {
  "base": "light",
  "brandTitle": "Dinner Rush",
  "brandUrl": "/",
  "colorPrimary": "#B04E0C",
  "colorSecondary": "#B04E0C",
  "appBg": "#F4F6FA",
  "appContentBg": "#FFFFFF",
  "appBorderColor": "#E2E7F0",
  "appBorderRadius": 4,
  "textColor": "#0E1420",
  "textInverseColor": "#0E1420",
  "barTextColor": "#4A5568",
  "barSelectedColor": "#B04E0C",
  "barBg": "#FFFFFF",
  "inputBg": "#EAEEF5",
  "inputBorder": "#C8D0DE",
  "inputTextColor": "#0E1420",
  "inputBorderRadius": 2,
  "fontBase": "'Inter var', system-ui, sans-serif",
  "fontCode": "'JetBrains Mono', ui-monospace, monospace"
} as const;

export const storybookThemeDark = create(darkThemeVars);
export const storybookThemeLight = create(lightThemeVars);
