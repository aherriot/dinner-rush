import "@testing-library/jest-dom/vitest";

// jsdom has no layout engine, so it never implements ResizeObserver. Headless
// UI's Listbox/Combobox use one to track option positions; a no-op is enough
// for jsdom-based interaction tests, which don't assert on layout.
class NoopResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
}

globalThis.ResizeObserver ??= NoopResizeObserver as unknown as typeof ResizeObserver;
