import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

interface StoryIndexEntry {
  id: string;
  type: string;
  title: string;
  name: string;
}

interface StoryIndex {
  entries: Record<string, StoryIndexEntry>;
}

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL ?? "http://localhost:6006";

async function fetchStories(): Promise<StoryIndexEntry[]> {
  const response = await fetch(`${BASE_URL}/index.json`);
  const index = (await response.json()) as StoryIndex;
  return Object.values(index.entries)
    .filter((entry) => entry.type === "story")
    .sort((a, b) => a.id.localeCompare(b.id));
}

const THEMES = ["dark", "light"] as const;

const stories = await fetchStories();

test.describe("Storybook stories", () => {
  for (const story of stories) {
    for (const theme of THEMES) {
      test(`${story.id} — ${theme}`, async ({ page }) => {
        // `SystemMap` lists real, unbounded-length content (a database's
        // real tables, Redis's real streams/groups) directly on its nodes —
        // its natural height varies with that data and can exceed the
        // default 1280x720 viewport in Storybook's canvas (which, unlike
        // the real board's grid, gives it no fixed parent height to fit
        // within). A *taller fixed viewport* handles this, not
        // `fullPage: true`: fullPage's image dimensions come from the
        // page's actual rendered height, which drifts by a couple of
        // pixels across environments with slightly different font
        // rendering (this repo's own CI runs Playwright on plain
        // `ubuntu-latest`, not the pinned Docker image baselines are
        // generated in) — a dimension mismatch fails the screenshot
        // comparison outright, before the existing 2%
        // `maxDiffPixelRatio` tolerance ever gets a chance to absorb it.
        // A fixed, generously-tall viewport keeps the captured image
        // dimensions identical regardless of that drift.
        if (story.id.startsWith("components-systemmap")) {
          await page.setViewportSize({ width: 1280, height: 1000 });
        }
        await page.goto(`/iframe.html?id=${story.id}&viewMode=story&globals=theme:${theme}`);
        await page.waitForLoadState("networkidle");
        const root = page.locator("#storybook-root");
        await expect(root).toBeVisible();

        const results = await new AxeBuilder({ page }).include("#storybook-root").analyze();
        expect(results.violations, results.violations.map((v) => `${v.id}: ${v.help}`).join("\n")).toEqual([]);

        await expect(page).toHaveScreenshot(`${story.id}-${theme}.png`);
      });
    }
  }
});
