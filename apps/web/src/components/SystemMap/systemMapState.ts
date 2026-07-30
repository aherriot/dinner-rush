import type {
  DispatchCourierRaw,
  DispatchTripRaw,
  KitchenOvenRaw,
} from "../../pages/Board/boardState";

export type NodeId =
  | "simulator"
  | "browser"
  | "front-of-house"
  | "kitchen"
  | "dispatch"
  | "redis"
  | "front-of-house-db"
  | "kitchen-db"
  | "dispatch-db";

export type EdgeId =
  | "client-front-of-house"
  | "browser-front-of-house-http"
  | "browser-front-of-house-ws"
  | "front-of-house-kitchen"
  | "front-of-house-dispatch"
  | "front-of-house-redis"
  | "kitchen-redis"
  | "dispatch-redis"
  | "front-of-house-front-of-house-db"
  | "kitchen-kitchen-db"
  | "dispatch-dispatch-db";

export type ServiceHealth = "healthy" | "degraded" | "down" | "unknown";

export interface NodeDef {
  id: NodeId;
  label: string;
  /** Kept short on purpose — it renders directly on a fixed-width node box
   * (`SystemMap.tsx`'s `NODE_WIDTH`/`DB_NODE_WIDTH`), not in a scrolling or
   * wrapping container. The fuller story lives in `detail`, shown only on
   * hover. */
  sublabel: string;
  detail: string;
  kind: "service" | "database";
  /** Real table names — `\dt` against the running database, not a guess at
   * Django/SQLAlchemy naming conventions (verified 2026-07-30). Domain
   * tables only; Django's own `auth_*`/`django_*` admin/migration tables
   * and each service's `alembic_version` are framework plumbing, omitted
   * as noise rather than domain state. Only set for `kind: "database"`
   * nodes — `SystemMap.tsx` lists every one of these directly on the node
   * (not hidden behind a hover tooltip), and its column-level detail
   * (types, primary/foreign keys) lives in `schemaData.ts`, shown in full
   * in the modal a click on the node opens. */
  tables?: string[];
}

export const SYSTEM_NODES: NodeDef[] = [
  {
    id: "simulator",
    label: "Simulator",
    sublabel: "No DB · no creds",
    detail:
      "Ordinary API client — no DB credentials, no service token, imports nothing from services/.",
    kind: "service",
  },
  {
    id: "front-of-house",
    label: "Front of House",
    sublabel: "Django/DRF · :8000",
    detail: "Django + DRF + Channels on :8000.",
    kind: "service",
  },
  {
    id: "browser",
    label: "Board (you)",
    sublabel: "This browser",
    detail: "This browser, viewing the board.",
    kind: "service",
  },
  {
    id: "kitchen",
    label: "Kitchen",
    sublabel: "FastAPI · :8001",
    detail: "FastAPI + Celery on :8001.",
    kind: "service",
  },
  {
    id: "redis",
    label: "Redis",
    sublabel: "Streams/cache/GEO",
    detail: "Streams (event bus), a read cache, and dispatch's GEO index. Click for the full topology.",
    kind: "service",
  },
  {
    id: "dispatch",
    label: "Dispatch",
    sublabel: "FastAPI · :8002",
    detail: "FastAPI + Redis GEO on :8002.",
    kind: "service",
  },
  {
    id: "front-of-house-db",
    label: "front_of_house",
    sublabel: "Postgres 16",
    detail: "Not shared with kitchen or dispatch (CLAUDE.md §3). Click for the entity relationships.",
    kind: "database",
    tables: [
      "accounts_staff",
      "catalog_menuitem",
      "customers_customer",
      "customers_address",
      "orders_order",
      "orders_orderitem",
      "orders_orderstatusevent",
      "orders_ordercodesequence",
      "eventing_eventtypecounter",
      "outbox",
      "processed_event",
    ],
  },
  {
    id: "kitchen-db",
    label: "kitchen",
    sublabel: "Postgres 16",
    detail: "No customer PII, not filtered but absent (CLAUDE.md §5). Click for the entity relationships.",
    kind: "database",
    tables: ["oven", "oven_slot", "station", "ticket", "outbox", "processed_event"],
  },
  {
    id: "dispatch-db",
    label: "dispatch",
    sublabel: "Postgres 16",
    detail: "Click for the entity relationships.",
    kind: "database",
    tables: ["courier", "trip", "address_grant", "pending_dropoff", "outbox", "processed_event"],
  },
];

export interface EdgeDef {
  id: EdgeId;
  from: NodeId;
  to: NodeId;
  kind: "http" | "ws" | "event" | "db";
  label: string;
}

/**
 * The real topology, not a decorative one — verified against
 * `services/*\/src` rather than assumed (DECISIONS.md §0003/§0004):
 * kitchen and dispatch never receive an HTTP push for domain events, they
 * consume `events:order` themselves (`cg:kitchen`, `cg:dispatch`);
 * front-of-house's only synchronous calls out are the kitchen capacity
 * quote and the read-only board queries against dispatch. The three `"db"`
 * edges are structural ownership, not traffic — they never carry a pulse
 * (`kind` drives that in `SystemMap.tsx`), same as a foreign-key line in an
 * ER diagram.
 */
export const SYSTEM_EDGES: EdgeDef[] = [
  {
    id: "client-front-of-house",
    from: "simulator",
    to: "front-of-house",
    kind: "http",
    label: "place order",
  },
  {
    id: "browser-front-of-house-http",
    from: "browser",
    to: "front-of-house",
    kind: "http",
    label: "snapshot · admin",
  },
  {
    id: "browser-front-of-house-ws",
    from: "browser",
    to: "front-of-house",
    kind: "ws",
    label: "live events",
  },
  {
    id: "front-of-house-kitchen",
    from: "front-of-house",
    to: "kitchen",
    kind: "http",
    label: "capacity quote",
  },
  {
    id: "front-of-house-dispatch",
    from: "front-of-house",
    to: "dispatch",
    kind: "http",
    label: "board reads",
  },
  {
    id: "front-of-house-redis",
    from: "front-of-house",
    to: "redis",
    kind: "event",
    label: "events:order",
  },
  {
    id: "kitchen-redis",
    from: "kitchen",
    to: "redis",
    kind: "event",
    label: "events:order · events:oven",
  },
  {
    id: "dispatch-redis",
    from: "dispatch",
    to: "redis",
    kind: "event",
    label: "events:order · events:courier",
  },
  {
    id: "front-of-house-front-of-house-db",
    from: "front-of-house",
    to: "front-of-house-db",
    kind: "db",
    label: "",
  },
  { id: "kitchen-kitchen-db", from: "kitchen", to: "kitchen-db", kind: "db", label: "" },
  { id: "dispatch-dispatch-db", from: "dispatch", to: "dispatch-db", kind: "db", label: "" },
];

export interface SystemHealthInput {
  /** `true` once the board has loaded a snapshot at least once. */
  hasSnapshot: boolean;
  snapshotFailed: boolean;
  wsConnected: boolean;
  ovens: KitchenOvenRaw[] | null;
  couriers: DispatchCourierRaw[] | null;
  /** Orders placed within a short trailing window — the only honest signal
   * the board has that *something* is generating load, since the simulator
   * is an ordinary API client with no channel back to the browser
   * (CLAUDE.md §"The simulator"). */
  recentOrderCount: number;
}

/**
 * One row per node, computed from data the board already holds — nothing
 * here is a new probe. Kitchen/dispatch "down" mirrors exactly what
 * `KitchenPanel`/`DispatchPanel` already call unreachable
 * (`data.ovens`/`data.couriers` being `null`, `boardState.ts`); "degraded"
 * is new — every oven down or every courier offline is the kitchen/dispatch
 * *answering* but at zero effective capacity, which is a different, more
 * interesting story for a chaos-scenario demo than a blunt reachability
 * bit.
 *
 * Each service's database node is given the exact same health as its owner
 * rather than "unknown" — not because the browser independently probed
 * Postgres, but because it doesn't need to: nearly every request these
 * services answer is a Postgres round trip (the capacity quote, the board
 * reads, the snapshot), so "front-of-house answered" already *is* evidence
 * its database answered. `SystemMap.tsx`'s tooltip on each database node
 * says so explicitly, so this inference is disclosed, not hidden.
 */
export function computeNodeHealth(input: SystemHealthInput): Record<NodeId, ServiceHealth> {
  const frontOfHouseDown = input.hasSnapshot === false && input.snapshotFailed;
  const frontOfHouse: ServiceHealth = frontOfHouseDown
    ? "down"
    : input.wsConnected
      ? "healthy"
      : "degraded";

  const kitchen: ServiceHealth =
    input.ovens === null
      ? "down"
      : input.ovens.length > 0 && input.ovens.every((oven) => oven.status === "down")
        ? "degraded"
        : "healthy";

  const dispatch: ServiceHealth =
    input.couriers === null
      ? "down"
      : input.couriers.length > 0 && input.couriers.every((courier) => courier.status === "offline")
        ? "degraded"
        : "healthy";

  // Redis Streams itself has no browser-visible probe — the websocket
  // fanout (`cg:ws-fanout`) is downstream of it, so "is the board's socket
  // up" is the closest honest proxy available from here.
  const redis: ServiceHealth = input.wsConnected ? "healthy" : "degraded";
  const browser: ServiceHealth = input.wsConnected ? "healthy" : "degraded";
  const simulator: ServiceHealth = input.recentOrderCount > 0 ? "healthy" : "unknown";

  return {
    "front-of-house": frontOfHouse,
    kitchen,
    dispatch,
    redis,
    browser,
    simulator,
    "front-of-house-db": frontOfHouse,
    "kitchen-db": kitchen,
    "dispatch-db": dispatch,
  };
}

export interface SystemMetricsInput {
  /** The board's own rolling-minute rate (`boardState.ordersPerMinute`) —
   * reused rather than recomputed so the number on this diagram never
   * disagrees with the one already on the status bar. */
  ordersPerMinute: number;
  ovens: KitchenOvenRaw[] | null;
  trips: DispatchTripRaw[] | null;
  couriers: DispatchCourierRaw[] | null;
  recentOrderCount: number;
}

/** Verified directly against the running stack, not the early planning doc
 * (DECISIONS.md §0003 lists 5 groups and no `cg:order-sync`/
 * `cg:ws-board-fanout` — both real, both added after that doc was written):
 * `docker exec redis-1 redis-cli XINFO GROUPS events:order` (etc. for the
 * other two streams) lists `cg:analytics`, `cg:dispatch`, `cg:kitchen`,
 * `cg:order-sync`, `cg:ws-board-fanout`, `cg:ws-fanout` — 6 distinct group
 * names, not 5. Fixed by design, not computed per render. */
/**
 * A short, second line of real state for each node beyond "healthy and on
 * this port" — one metric per node, each already computed elsewhere on the
 * board (`ordersPerMinute`, the oven slot data `KitchenPanel` renders, the
 * trip/courier lists `DispatchPanel`/`CourierQueue` render) and reused here
 * rather than re-derived, so this diagram can never show a number that
 * disagrees with the panel it came from. `undefined` for a node this input
 * has no data for yet (the caller renders nothing rather than a
 * placeholder zero). Redis and the database nodes have no entry here —
 * they list their real tables/streams/groups directly on the node instead
 * of a summarising count (`SystemMap.tsx`'s `RedisNode`/`DatabaseNode`).
 */
export function computeNodeMetrics(input: SystemMetricsInput): Partial<Record<NodeId, string>> {
  const metrics: Partial<Record<NodeId, string>> = {
    "front-of-house": `${input.ordersPerMinute} order${input.ordersPerMinute === 1 ? "" : "s"}/min`,
    simulator: `${input.recentOrderCount} order${input.recentOrderCount === 1 ? "" : "s"}/15s`,
  };

  if (input.ovens !== null) {
    const slots = input.ovens.flatMap((oven) => oven.slots);
    const busy = slots.filter((slot) => slot.order_id !== null).length;
    metrics.kitchen = `${busy}/${slots.length} slots busy`;
  }

  if (input.couriers !== null) {
    const tripCount = input.trips?.length ?? 0;
    metrics.dispatch = `${tripCount} active trip${tripCount === 1 ? "" : "s"}`;
  }

  return metrics;
}

const PRODUCER_PREFIX_TO_NODE: Record<string, NodeId> = {
  front_of_house: "front-of-house",
  kitchen: "kitchen",
  dispatch: "dispatch",
};

/** `producer` is `"kitchen@1.4.2"` (DECISIONS.md §0004's envelope) — the
 * part before `@` names the service that actually published the event. */
export function producerNodeIdFor(producer: string): NodeId | null {
  const prefix = producer.split("@")[0];
  return PRODUCER_PREFIX_TO_NODE[prefix] ?? null;
}

export interface PulseStep {
  edgeId: EdgeId;
  delayMs: number;
}

/** Roughly `--dur-slow` (DESIGN.md §6) — a plain constant rather than the
 * CSS custom property because SMIL `<animate dur>` can't read a CSS
 * variable; the reduced-motion case is handled separately by skipping the
 * animated dot entirely (`SystemMap.tsx`), not by this value. */
export const PULSE_STAGE_MS = 260;

const PRODUCER_EDGE: Partial<Record<NodeId, EdgeId>> = {
  kitchen: "kitchen-redis",
  dispatch: "dispatch-redis",
};

/**
 * Reconstructs the real hop-by-hop path a live event just took to reach
 * this board, from fields already on the envelope — not a decorative
 * animation. `kitchen`/`dispatch` publish to their own outbox, which a
 * relay carries onto `events:*` on Redis Streams; front-of-house's
 * `cg:ws-fanout` consumer reads it back off Streams and pushes it down the
 * socket this board already holds open (DECISIONS.md §0003/§0004). An
 * event front-of-house produced itself
 * (`order.placed`/`order.accepted`/`order.rejected`) skips the first hop
 * because there isn't one.
 */
export function pulsePlanForEvent(event: { producer: string }): PulseStep[] {
  const producerNode = producerNodeIdFor(event.producer);
  const producerEdge = producerNode ? PRODUCER_EDGE[producerNode] : undefined;

  const steps: PulseStep[] = [];
  let delay = 0;
  if (producerEdge) {
    steps.push({ edgeId: producerEdge, delayMs: delay });
    delay += PULSE_STAGE_MS;
  }
  steps.push({ edgeId: "front-of-house-redis", delayMs: delay });
  delay += PULSE_STAGE_MS;
  steps.push({ edgeId: "browser-front-of-house-ws", delayMs: delay });
  return steps;
}

const EVENT_HTTP_EDGE: Partial<Record<string, EdgeId>> = {
  "order.placed": "client-front-of-house",
  "order.accepted": "front-of-house-kitchen",
  "order.rejected": "front-of-house-kitchen",
};

/** The synchronous HTTP leg alongside an event, when that event is the
 * direct result of one: a new order arriving through the public API, or
 * front-of-house's capacity-quote call to kitchen resolving accept/reject
 * (`kitchen_client.py`). Independent of `pulsePlanForEvent`'s Streams path —
 * both can and do fire for the same event. */
export function httpPulseForEventType(eventType: string): EdgeId | null {
  return EVENT_HTTP_EDGE[eventType] ?? null;
}

/** Fired directly by the board's own snapshot poll (`Board.tsx`'s
 * `fetchSnapshot`), not derived from a socket event — `GET
 * /api/v1/board/snapshot` is front-of-house aggregating a read from each of
 * kitchen and dispatch in the same request. */
export const SNAPSHOT_PULSE_EDGES: EdgeId[] = [
  "browser-front-of-house-http",
  "front-of-house-kitchen",
  "front-of-house-dispatch",
];

/** Fired by an admin action from the board itself (speed change, starting
 * or stopping a chaos scenario) — a `POST` to front-of-house, nothing more. */
export const ADMIN_PULSE_EDGES: EdgeId[] = ["browser-front-of-house-http"];

const SIMULATOR_ACTIVITY_WINDOW_MS = 15_000;

/** How many orders were placed in the last `SIMULATOR_ACTIVITY_WINDOW_MS` —
 * the input to `computeNodeHealth`'s `recentOrderCount`, kept separate so
 * it's independently testable against a fixed `nowMs`. */
export function recentOrderCount(placedAtTimes: number[], nowMs: number): number {
  return placedAtTimes.filter((placedAt) => nowMs - placedAt <= SIMULATOR_ACTIVITY_WINDOW_MS).length;
}
