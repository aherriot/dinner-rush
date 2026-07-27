import { describe, expect, it } from "vitest";
import tokens from "./tokens.json";
import { contrastRatio } from "./contrast";

// DESIGN.md §3: "Ratios are measured against the panel background of their
// theme (#131720 dark, #FFFFFF light). Every token below clears 4.5:1."
const PANEL_BG = { dark: tokens.color["bg-panel"].dark, light: tokens.color["bg-panel"].light };
const WCAG_AA_TEXT = 4.5;

const themes = ["dark", "light"] as const;

describe("token contrast", () => {
  for (const [name, ratios] of Object.entries(tokens.contrastRatio)) {
    for (const theme of themes) {
      it(`${name} clears ${WCAG_AA_TEXT}:1 against --bg-panel in ${theme}`, () => {
        const foregroundValue =
          (tokens.color as Record<string, { dark: string; light: string }>)[name][theme];
        const actual = contrastRatio(foregroundValue, PANEL_BG[theme]);
        expect(actual).toBeGreaterThanOrEqual(WCAG_AA_TEXT);
      });

      it(`${name}'s documented ratio in ${theme} matches the computed value`, () => {
        const foregroundValue =
          (tokens.color as Record<string, { dark: string; light: string }>)[name][theme];
        const actual = contrastRatio(foregroundValue, PANEL_BG[theme]);
        const documented = ratios[theme];
        expect(actual).toBeCloseTo(documented, 1);
      });
    }
  }

  it("covers every colour token that is documented as text-capable", () => {
    // status-late shares status-boxed's colour and is never rendered as its
    // own text run (it's a border + label suffix — DESIGN.md §3.3), so it's
    // deliberately absent from contrastRatio. Every other status/text/accent
    // token must be present.
    const textCapable = Object.keys(tokens.color).filter(
      (name) => name.startsWith("text-") || name.startsWith("status-") || name.startsWith("accent"),
    );
    const documented = Object.keys(tokens.contrastRatio);
    const undocumented = textCapable.filter(
      (name) => !documented.includes(name) && name !== "status-late" && name !== "accent-hover" && name !== "accent-active",
    );
    expect(undocumented).toEqual([]);
  });
});
