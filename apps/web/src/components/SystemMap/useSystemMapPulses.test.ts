import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useSystemMapPulses } from "./useSystemMapPulses";

const DURATION_MS = 200;

describe("useSystemMapPulses", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("stages a kitchen-produced event across its edges in order, then clears each one", () => {
    const { result } = renderHook(() => useSystemMapPulses(DURATION_MS));

    act(() => {
      result.current.notifyEvent({ producer: "kitchen@1.0.0", event_type: "order.baking" });
    });

    expect(result.current.pulses.map((p) => p.edgeId)).toEqual(["kitchen-redis"]);

    act(() => {
      vi.advanceTimersByTime(260);
    });
    expect(result.current.pulses.map((p) => p.edgeId)).toEqual(
      expect.arrayContaining(["front-of-house-redis"]),
    );

    act(() => {
      vi.advanceTimersByTime(260);
    });
    expect(result.current.pulses.map((p) => p.edgeId)).toEqual(
      expect.arrayContaining(["browser-front-of-house-ws"]),
    );

    act(() => {
      vi.advanceTimersByTime(DURATION_MS + 1);
    });
    expect(result.current.pulses).toEqual([]);
  });

  it("also fires the capacity-quote HTTP edge for order.accepted", () => {
    const { result } = renderHook(() => useSystemMapPulses(DURATION_MS));

    act(() => {
      result.current.notifyEvent({ producer: "front_of_house@1.0.0", event_type: "order.accepted" });
    });

    expect(result.current.pulses.map((p) => p.edgeId)).toEqual(
      expect.arrayContaining(["front-of-house-redis", "front-of-house-kitchen"]),
    );
  });

  it("notifyEdges fires the given edges immediately", () => {
    const { result } = renderHook(() => useSystemMapPulses(DURATION_MS));

    act(() => {
      result.current.notifyEdges(["browser-front-of-house-http", "front-of-house-dispatch"]);
    });

    expect(result.current.pulses.map((p) => p.edgeId).sort()).toEqual(
      ["browser-front-of-house-http", "front-of-house-dispatch"].sort(),
    );

    act(() => {
      vi.advanceTimersByTime(DURATION_MS + 1);
    });
    expect(result.current.pulses).toEqual([]);
  });

  it("clears pending timers on unmount without throwing", () => {
    const { result, unmount } = renderHook(() => useSystemMapPulses(DURATION_MS));

    act(() => {
      result.current.notifyEvent({ producer: "dispatch@1.0.0", event_type: "order.delivering" });
    });

    expect(() => unmount()).not.toThrow();
    expect(() => vi.advanceTimersByTime(2000)).not.toThrow();
  });
});
