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
