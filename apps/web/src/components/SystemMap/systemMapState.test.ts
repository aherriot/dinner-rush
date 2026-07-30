import { describe, expect, it } from "vitest";
import {
  ADMIN_PULSE_EDGES,
  SNAPSHOT_PULSE_EDGES,
  SYSTEM_EDGES,
  SYSTEM_NODES,
  computeNodeHealth,
  computeNodeMetrics,
  httpPulseForEventType,
  producerNodeIdFor,
  pulsePlanForEvent,
  recentOrderCount,
  type SystemHealthInput,
  type SystemMetricsInput,
} from "./systemMapState";

const BASE_INPUT: SystemHealthInput = {
  hasSnapshot: true,
  snapshotFailed: false,
  wsConnected: true,
  ovens: [{ id: "o1", name: "Oven 1", slot_count: 2, status: "available", slots: [] }],
  couriers: [{ id: "c1", name: "Courier 1", status: "idle", x: 1, y: 1 }],
  recentOrderCount: 1,
};

describe("computeNodeHealth", () => {
  it("reports every node healthy when the board is fully connected", () => {
    const health = computeNodeHealth(BASE_INPUT);
    expect(health).toEqual({
      gateway: "healthy",
      kitchen: "healthy",
      dispatch: "healthy",
      redis: "healthy",
      browser: "healthy",
      simulator: "healthy",
      "gateway-db": "healthy",
      "kitchen-db": "healthy",
      "dispatch-db": "healthy",
    });
  });

  it("mirrors each service's health onto its own database node", () => {
    const health = computeNodeHealth({ ...BASE_INPUT, ovens: null, couriers: null });
    expect(health["gateway-db"]).toBe(health.gateway);
    expect(health["kitchen-db"]).toBe(health.kitchen);
    expect(health["dispatch-db"]).toBe(health.dispatch);
    expect(health["kitchen-db"]).toBe("down");
    expect(health["dispatch-db"]).toBe("down");
  });

  it("marks gateway down only on a cold-load snapshot failure, not a later one", () => {
    const health = computeNodeHealth({ ...BASE_INPUT, hasSnapshot: false, snapshotFailed: true });
    expect(health.gateway).toBe("down");
  });

  it("marks gateway (and redis/browser) degraded, not down, when only the websocket is disconnected", () => {
    const health = computeNodeHealth({ ...BASE_INPUT, wsConnected: false });
    expect(health.gateway).toBe("degraded");
    expect(health.redis).toBe("degraded");
    expect(health.browser).toBe("degraded");
  });

  it("marks kitchen down when the board has never gotten oven data", () => {
    const health = computeNodeHealth({ ...BASE_INPUT, ovens: null });
    expect(health.kitchen).toBe("down");
  });

  it("marks kitchen degraded, not down, when it answers but every oven is out of service", () => {
    const health = computeNodeHealth({
      ...BASE_INPUT,
      ovens: [{ id: "o1", name: "Oven 1", slot_count: 2, status: "down", slots: [] }],
    });
    expect(health.kitchen).toBe("degraded");
  });

  it("marks dispatch down when the board has never gotten courier data", () => {
    const health = computeNodeHealth({ ...BASE_INPUT, couriers: null });
    expect(health.dispatch).toBe("down");
  });

  it("marks dispatch degraded when it answers but every courier is offline", () => {
    const health = computeNodeHealth({
      ...BASE_INPUT,
      couriers: [{ id: "c1", name: "Courier 1", status: "offline", x: null, y: null }],
    });
    expect(health.dispatch).toBe("degraded");
  });

  it("marks the simulator unknown, not down, when nothing has arrived recently", () => {
    const health = computeNodeHealth({ ...BASE_INPUT, recentOrderCount: 0 });
    expect(health.simulator).toBe("unknown");
  });
});

describe("producerNodeIdFor", () => {
  it("maps a versioned producer string to its service", () => {
    expect(producerNodeIdFor("kitchen@1.4.2")).toBe("kitchen");
    expect(producerNodeIdFor("dispatch@0.9.0")).toBe("dispatch");
    expect(producerNodeIdFor("gateway@1.4.2")).toBe("gateway");
  });

  it("returns null for an unrecognised producer rather than guessing", () => {
    expect(producerNodeIdFor("mystery-service@1.0.0")).toBeNull();
  });
});

describe("pulsePlanForEvent", () => {
  it("routes a kitchen-produced event through kitchen->redis->gateway->browser", () => {
    const steps = pulsePlanForEvent({ producer: "kitchen@1.4.2" });
    expect(steps.map((s) => s.edgeId)).toEqual(["kitchen-redis", "gateway-redis", "browser-gateway-ws"]);
    expect(steps[0].delayMs).toBeLessThan(steps[1].delayMs);
    expect(steps[1].delayMs).toBeLessThan(steps[2].delayMs);
  });

  it("routes a dispatch-produced event through dispatch->redis->gateway->browser", () => {
    const steps = pulsePlanForEvent({ producer: "dispatch@0.9.0" });
    expect(steps.map((s) => s.edgeId)).toEqual(["dispatch-redis", "gateway-redis", "browser-gateway-ws"]);
  });

  it("skips the missing first hop for an event gateway produced itself", () => {
    const steps = pulsePlanForEvent({ producer: "gateway@1.4.2" });
    expect(steps.map((s) => s.edgeId)).toEqual(["gateway-redis", "browser-gateway-ws"]);
  });

  it("still reaches the browser for an unrecognised producer", () => {
    const steps = pulsePlanForEvent({ producer: "mystery@1.0.0" });
    expect(steps.map((s) => s.edgeId)).toEqual(["gateway-redis", "browser-gateway-ws"]);
  });
});

describe("httpPulseForEventType", () => {
  it("maps order.placed to the client-facing edge", () => {
    expect(httpPulseForEventType("order.placed")).toBe("client-gateway");
  });

  it("maps order.accepted and order.rejected to the capacity-quote edge", () => {
    expect(httpPulseForEventType("order.accepted")).toBe("gateway-kitchen");
    expect(httpPulseForEventType("order.rejected")).toBe("gateway-kitchen");
  });

  it("returns null for event types with no synchronous HTTP counterpart", () => {
    expect(httpPulseForEventType("order.baking")).toBeNull();
  });
});

describe("recentOrderCount", () => {
  it("counts only placements within the trailing window", () => {
    const now = 100_000;
    expect(recentOrderCount([now - 1_000, now - 20_000], now)).toBe(1);
  });

  it("returns 0 for an empty order list", () => {
    expect(recentOrderCount([], 100_000)).toBe(0);
  });
});

describe("computeNodeMetrics", () => {
  const BASE_METRICS_INPUT: SystemMetricsInput = {
    ordersPerMinute: 12,
    ovens: [
      {
        id: "o1",
        name: "Oven 1",
        slot_count: 2,
        status: "available",
        slots: [
          { id: "s1", slot_index: 0, order_id: "abc", claimed_at: null, frees_at: null },
          { id: "s2", slot_index: 1, order_id: null, claimed_at: null, frees_at: null },
        ],
      },
    ],
    trips: [
      {
        id: "t1",
        code: "4471",
        status: "delivering",
        courier_id: "c1",
        pickup_x: 50,
        pickup_y: 50,
        dropoff_x: 60,
        dropoff_y: 40,
        assigned_at: "2024-01-01T00:00:00Z",
        eta_at: "2024-01-01T00:10:00Z",
      },
    ],
    couriers: [{ id: "c1", name: "Courier 1", status: "delivering", x: 60, y: 40 }],
    recentOrderCount: 2,
  };

  it("reuses the board's own orders/min and simulator recent count", () => {
    const metrics = computeNodeMetrics(BASE_METRICS_INPUT);
    expect(metrics.gateway).toBe("12 orders/min");
    expect(metrics.simulator).toBe("2 orders/15s");
  });

  it("has no entry for redis or the database nodes — they list their real state directly", () => {
    const metrics = computeNodeMetrics(BASE_METRICS_INPUT);
    expect(metrics.redis).toBeUndefined();
    expect(metrics["gateway-db"]).toBeUndefined();
    expect(metrics["kitchen-db"]).toBeUndefined();
    expect(metrics["dispatch-db"]).toBeUndefined();
  });

  it("counts busy vs total oven slots across every oven", () => {
    const metrics = computeNodeMetrics(BASE_METRICS_INPUT);
    expect(metrics.kitchen).toBe("1/2 slots busy");
  });

  it("counts active trips for dispatch", () => {
    const metrics = computeNodeMetrics(BASE_METRICS_INPUT);
    expect(metrics.dispatch).toBe("1 active trip");
  });

  it("uses singular/plural correctly at the boundary", () => {
    const metrics = computeNodeMetrics({ ...BASE_METRICS_INPUT, ordersPerMinute: 1, trips: [] });
    expect(metrics.gateway).toBe("1 order/min");
    expect(metrics.dispatch).toBe("0 active trips");
  });

  it("omits kitchen/dispatch metrics entirely when the board has no data for them", () => {
    const metrics = computeNodeMetrics({ ...BASE_METRICS_INPUT, ovens: null, couriers: null });
    expect(metrics.kitchen).toBeUndefined();
    expect(metrics.dispatch).toBeUndefined();
  });

});

describe("topology data", () => {
  it("every edge references two node ids that actually exist", () => {
    const nodeIds = new Set(SYSTEM_NODES.map((n) => n.id));
    for (const edge of SYSTEM_EDGES) {
      expect(nodeIds.has(edge.from)).toBe(true);
      expect(nodeIds.has(edge.to)).toBe(true);
    }
  });

  it("has no duplicate node or edge ids", () => {
    expect(new Set(SYSTEM_NODES.map((n) => n.id)).size).toBe(SYSTEM_NODES.length);
    expect(new Set(SYSTEM_EDGES.map((e) => e.id)).size).toBe(SYSTEM_EDGES.length);
  });

  it("only points snapshot/admin pulses at edges that exist", () => {
    const edgeIds = new Set(SYSTEM_EDGES.map((e) => e.id));
    for (const id of [...SNAPSHOT_PULSE_EDGES, ...ADMIN_PULSE_EDGES]) {
      expect(edgeIds.has(id)).toBe(true);
    }
  });
});
