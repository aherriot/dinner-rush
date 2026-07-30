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

// jsdom doesn't implement matchMedia at all. `SystemMap`'s reduced-motion
// check (and any future one) needs it to exist; defaulting `matches: false`
// keeps existing tests on the animated code path unless a test overrides
// `window.matchMedia` itself for a reduced-motion case.
globalThis.matchMedia ??=
  function matchMedia(query: string): MediaQueryList {
    return {
      matches: false,
      media: query,
      onchange: null,
      addListener: () => {},
      removeListener: () => {},
      addEventListener: () => {},
      removeEventListener: () => {},
      dispatchEvent: () => false,
    } as MediaQueryList;
  } as typeof window.matchMedia;
