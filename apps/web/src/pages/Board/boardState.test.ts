import { describe, expect, it } from "vitest";
import type { BoardEnvelope } from "./useBoardSocket";
import {
  applyOrderEvent,
  formatRelativeTime,
  lateRatioPercent,
  mapCouriers,
  mapOvens,
  ordersPerMinute,
  toOrderFeedRows,
  toTimelineEvent,
  type BoardOrder,
  type DispatchCourierRaw,
  type KitchenOvenRaw,
} from "./boardState";

function event(overrides: Partial<BoardEnvelope> & { event_type: string }): BoardEnvelope {
  return {
    event_id: "evt-1",
    event_version: 1,
    occurred_at: "2026-01-01T00:00:00Z",
    aggregate_type: "order",
    aggregate_id: "agg-1",
    sequence: 1,
    correlation_id: "corr-1",
    causation_id: null,
    producer: "gateway@0.1.0",
    payload: {},
    stream_id: "1700000000000-0",
    stream: "events:order",
    ...overrides,
  };
}

describe("applyOrderEvent", () => {
  it("inserts a new row on order.placed", () => {
    const result = applyOrderEvent([], event({ event_type: "order.placed", payload: { code: "4471" } }));
    expect(result).toEqual([{ code: "4471", status: "placed", late: false, placedAt: expect.any(Number) }]);
  });

  it("updates an existing row's status without touching other fields", () => {
    const orders: BoardOrder[] = [{ code: "4471", status: "placed", late: true, placedAt: 1000 }];
    const result = applyOrderEvent(orders, event({ event_type: "order.accepted", payload: { code: "4471" } }));
    expect(result).toEqual([{ code: "4471", status: "accepted", late: true, placedAt: 1000 }]);
  });

  it("maps courier.assigned to the assigned status", () => {
    const orders: BoardOrder[] = [{ code: "4471", status: "ready", late: false, placedAt: 1000 }];
    const result = applyOrderEvent(
      orders,
      event({ event_type: "courier.assigned", stream: "events:courier", payload: { code: "4471" } }),
    );
    expect(result[0].status).toBe("assigned");
  });

  it("maps order.unassigned back to ready", () => {
    const orders: BoardOrder[] = [{ code: "4471", status: "assigned", late: false, placedAt: 1000 }];
    const result = applyOrderEvent(orders, event({ event_type: "order.unassigned", payload: { code: "4471" } }));
    expect(result[0].status).toBe("ready");
  });

  it("ignores an update for a code it has never seen unless it's a new-row event", () => {
    const result = applyOrderEvent([], event({ event_type: "order.baking", payload: { code: "9999" } }));
    expect(result).toEqual([]);
  });

  it("ignores an unrecognised event type", () => {
    const orders: BoardOrder[] = [{ code: "4471", status: "placed", late: false, placedAt: 1000 }];
    const result = applyOrderEvent(orders, event({ event_type: "station.down", payload: {} }));
    expect(result).toBe(orders);
  });

  it("ignores a payload with no code", () => {
    const result = applyOrderEvent([], event({ event_type: "order.placed", payload: {} }));
    expect(result).toEqual([]);
  });

  it("doesn't throw when a recognised event type arrives with no payload at all", () => {
    // Omit rather than `delete` — simulates a network message that doesn't
    // match the type, without relying on `delete` being legal for a
    // required property (it isn't, under this tsconfig).
    const { payload, ...rest } = event({ event_type: "order.placed" });
    void payload;
    const malformed = rest as BoardEnvelope;
    expect(() => applyOrderEvent([], malformed)).not.toThrow();
    expect(applyOrderEvent([], malformed)).toEqual([]);
  });
});

describe("formatRelativeTime", () => {
  it("renders whole seconds under a minute", () => {
    expect(formatRelativeTime(1000, 1000 + 45_000)).toBe("45s ago");
  });

  it("renders whole minutes under an hour", () => {
    expect(formatRelativeTime(0, 3 * 60_000)).toBe("3m ago");
  });

  it("renders whole hours at an hour or beyond", () => {
    expect(formatRelativeTime(0, 2 * 60 * 60_000)).toBe("2h ago");
  });
});

describe("toOrderFeedRows", () => {
  it("projects the presentational fields and formats placedAt relative to now", () => {
    const orders: BoardOrder[] = [{ code: "4471", status: "placed", late: true, placedAt: 1000 }];
    expect(toOrderFeedRows(orders, 1000 + 12_000)).toEqual([
      { code: "4471", status: "placed", late: true, placedAgo: "12s ago" },
    ]);
  });
});

describe("toTimelineEvent", () => {
  it("projects a matching order event into the timeline shape", () => {
    const result = toTimelineEvent(
      event({ event_type: "order.accepted", occurred_at: "2026-01-01T00:00:05Z", payload: { code: "4471" } }),
      "4471",
    );
    expect(result).toEqual({
      event: "order.accepted",
      from_status: null,
      to_status: "accepted",
      occurred_at: "2026-01-01T00:00:05Z",
      reason: null,
      queue_depth: null,
    });
  });

  it("carries the rejection reason and queue depth for a rejected event", () => {
    const result = toTimelineEvent(
      event({
        event_type: "order.rejected",
        occurred_at: "2026-01-01T00:00:05Z",
        payload: { code: "4471", reason: "at_capacity", queue_depth: 42 },
      }),
      "4471",
    );
    expect(result).toEqual({
      event: "order.rejected",
      from_status: null,
      to_status: "rejected",
      occurred_at: "2026-01-01T00:00:05Z",
      reason: "at_capacity",
      queue_depth: 42,
    });
  });

  it("returns null for a different order's event", () => {
    const result = toTimelineEvent(
      event({ event_type: "order.accepted", payload: { code: "9999" } }),
      "4471",
    );
    expect(result).toBeNull();
  });

  it("returns null for an event type with no FSM status mapping", () => {
    const result = toTimelineEvent(event({ event_type: "station.down", payload: { code: "4471" } }), "4471");
    expect(result).toBeNull();
  });
});

describe("ordersPerMinute", () => {
  it("counts only orders placed within the last rolling minute", () => {
    const now = 120_000;
    const orders: BoardOrder[] = [
      { code: "1", status: "placed", late: false, placedAt: now - 10_000 },
      { code: "2", status: "placed", late: false, placedAt: now - 59_000 },
      { code: "3", status: "placed", late: false, placedAt: now - 61_000 },
    ];
    expect(ordersPerMinute(orders, now)).toBe(2);
  });
});

describe("lateRatioPercent", () => {
  it("is undefined when nothing is in flight", () => {
    const orders: BoardOrder[] = [{ code: "1", status: "delivered", late: false, placedAt: 0 }];
    expect(lateRatioPercent(orders)).toBeUndefined();
  });

  it("computes the percentage of in-flight orders flagged late", () => {
    const orders: BoardOrder[] = [
      { code: "1", status: "baking", late: true, placedAt: 0 },
      { code: "2", status: "baking", late: false, placedAt: 0 },
      { code: "3", status: "delivered", late: true, placedAt: 0 }, // terminal, excluded
    ];
    expect(lateRatioPercent(orders)).toBe(50);
  });
});

describe("mapOvens", () => {
  it("marks every slot down when the oven itself is down, regardless of occupancy", () => {
    const ovens: KitchenOvenRaw[] = [
      {
        id: "o1",
        name: "Oven 1",
        slot_count: 1,
        status: "down",
        slots: [{ id: "s1", slot_index: 0, order_id: "order-1", claimed_at: null, frees_at: null }],
      },
    ];
    expect(mapOvens(ovens, 0)[0].slots).toEqual([{ status: "down" }]);
  });

  it("computes bake progress from claimed_at/frees_at", () => {
    const ovens: KitchenOvenRaw[] = [
      {
        id: "o1",
        name: "Oven 1",
        slot_count: 1,
        status: "available",
        slots: [
          {
            id: "s1",
            slot_index: 0,
            order_id: "order-1",
            claimed_at: "2026-01-01T00:00:00.000Z",
            frees_at: "2026-01-01T00:01:00.000Z",
          },
        ],
      },
    ];
    const halfway = new Date("2026-01-01T00:00:30.000Z").getTime();
    expect(mapOvens(ovens, halfway)[0].slots).toEqual([{ status: "occupied", progress: 50 }]);
  });

  it("renders an unclaimed slot as free", () => {
    const ovens: KitchenOvenRaw[] = [
      {
        id: "o1",
        name: "Oven 1",
        slot_count: 1,
        status: "available",
        slots: [{ id: "s1", slot_index: 0, order_id: null, claimed_at: null, frees_at: null }],
      },
    ];
    expect(mapOvens(ovens, 0)[0].slots).toEqual([{ status: "free" }]);
  });

  it("returns an empty list when kitchen didn't answer", () => {
    expect(mapOvens(null, 0)).toEqual([]);
  });
});

describe("mapCouriers", () => {
  it("excludes couriers that have never reported a position", () => {
    const couriers: DispatchCourierRaw[] = [
      { id: "c1", name: "Ada", status: "idle", x: null, y: null },
      { id: "c2", name: "Grace", status: "idle", x: 10, y: 20 },
    ];
    const result = mapCouriers(couriers);
    expect(result).toHaveLength(1);
    expect(result[0].id).toBe("c2");
  });

  it("maps assigned and delivering to the active CourierDot status", () => {
    const couriers: DispatchCourierRaw[] = [
      { id: "c1", name: "Ada", status: "assigned", x: 1, y: 1 },
      { id: "c2", name: "Grace", status: "delivering", x: 2, y: 2 },
    ];
    const result = mapCouriers(couriers);
    expect(result.map((c) => c.status)).toEqual(["active", "active"]);
  });

  it("returns an empty list when dispatch didn't answer", () => {
    expect(mapCouriers(null)).toEqual([]);
  });
});
