import type { BacklogSummary, CourierRosterEntry } from "../../components/CourierQueue/CourierQueue";
import type { CourierMapEntry } from "../../components/DispatchPanel/DispatchPanel";
import type { CourierStatus } from "../../components/CourierDot/CourierDot";
import type { OvenViewModel } from "../../components/KitchenPanel/KitchenPanel";
import type { OvenSlotStatus } from "../../components/OvenSlot/OvenSlot";
import type { OrderFeedRow } from "../../components/OrderFeed/OrderFeed";
import type { TimelineEvent } from "../../components/OrderTimeline/OrderTimeline";
import type { OrderStatus } from "../../design/tokens";
import type { BoardEnvelope } from "./useBoardSocket";

export interface BoardOrder {
  code: string;
  status: OrderStatus;
  late: boolean;
  placedAt: number;
}

export interface KitchenOvenSlotRaw {
  id: string;
  slot_index: number;
  order_id: string | null;
  claimed_at: string | null;
  frees_at: string | null;
}

export interface KitchenOvenRaw {
  id: string;
  name: string;
  slot_count: number;
  status: "available" | "down";
  slots: KitchenOvenSlotRaw[];
}

export interface KitchenTicketRaw {
  id: string;
  code: string;
  status: string;
}

export interface DispatchCourierRaw {
  id: string;
  name: string;
  status: string;
  x: number | null;
  y: number | null;
}

export interface DispatchTripRaw {
  id: string;
  code: string;
  status: string;
  courier_id: string;
  pickup_x: number;
  pickup_y: number;
  dropoff_x: number;
  dropoff_y: number;
  assigned_at: string;
  eta_at: string;
}

export interface DispatchBacklogRaw {
  ready_count: number;
  oldest_waiting_seconds: number | null;
}

/** Every order-status-affecting event type maps to exactly one FSM status
 * (SPEC.md §2) — mirrors `gateway/eventing/handlers.py`'s own
 * `_EVENT_TYPE_TO_TRANSITION` table, since the board reads the same event
 * spine gateway's own order-sync consumer does. `courier.assigned` lives on
 * `events:courier` (DECISIONS.md §0003), not `events:order`, but is handled
 * identically here — this reducer switches on `event_type`, not on which
 * physical stream carried it. */
const ORDER_EVENT_STATUS: Record<string, OrderStatus> = {
  "order.placed": "placed",
  "order.accepted": "accepted",
  "order.rejected": "rejected",
  "order.queued": "queued",
  "order.baking": "baking",
  "order.baked": "boxed",
  "order.ready": "ready",
  "courier.assigned": "assigned",
  "order.picked_up": "picked_up",
  "order.delivering": "delivering",
  "order.delivered": "delivered",
  "order.failed": "failed",
  "order.unassigned": "ready",
};

/** `order.placed` always precedes every other order event for a given code,
 * so seeing anything else for a code we don't have means we missed the
 * placement (e.g. connected mid-order before the initial snapshot caught
 * up) — dropped rather than guessed, since fabricating fields the payload
 * doesn't carry would render a wrong summary line. `order.rejected` is
 * included defensively for the same cold-start case. */
const NEW_ROW_EVENT_TYPES = new Set(["order.placed", "order.rejected"]);

// Matches gateway's `BOARD_ORDER_FEED_LIMIT` (board/views.py) — the client
// cap must be at least the cold-load cap or a busy demo would visibly
// truncate below what the initial snapshot already showed.
export const ORDER_FEED_LIMIT = 500;

export function applyOrderEvent(orders: BoardOrder[], event: BoardEnvelope): BoardOrder[] {
  const status = ORDER_EVENT_STATUS[event.event_type];
  if (!status) return orders;
  const code = event.payload["code"];
  if (typeof code !== "string") return orders;

  const index = orders.findIndex((order) => order.code === code);
  if (index === -1) {
    if (!NEW_ROW_EVENT_TYPES.has(event.event_type)) return orders;
    const placedAt = new Date(event.occurred_at).getTime();
    return [{ code, status, late: false, placedAt }, ...orders].slice(0, ORDER_FEED_LIMIT);
  }

  const next = [...orders];
  next[index] = { ...next[index], status };
  return next;
}

/** "45s ago" / "3m ago" / "2h ago" — coarser than a live-updating stopwatch
 * on purpose, so it doesn't need its own re-render timer independent of the
 * board's existing `now` tick (`TICK_INTERVAL_MS`, `Board.tsx`). */
export function formatRelativeTime(pastMs: number, nowMs: number): string {
  const seconds = Math.max(0, Math.round((nowMs - pastMs) / 1000));
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.round(minutes / 60);
  return `${hours}h ago`;
}

export function toOrderFeedRows(orders: BoardOrder[], nowMs: number): OrderFeedRow[] {
  return orders.map(({ code, status, late, placedAt }) => ({
    code,
    status,
    late,
    placedAgo: formatRelativeTime(placedAt, nowMs),
  }));
}

/** Projects a live board event into the shape `OrderTimeline` renders, for
 * appending to an already-open drill-in without a refetch — `null` when the
 * event isn't for the order in question or isn't one of the FSM-affecting
 * types `ORDER_EVENT_STATUS` recognises. `from_status` isn't derivable from
 * a single event in isolation and isn't rendered by `OrderTimeline` anyway
 * (it only reads `to_status`/`occurred_at`), so it's left `null` rather than
 * tracked just to fill in a field nothing displays. */
export function toTimelineEvent(event: BoardEnvelope, code: string): TimelineEvent | null {
  const status = ORDER_EVENT_STATUS[event.event_type];
  if (!status) return null;
  if (event.payload["code"] !== code) return null;
  const reason = event.payload["reason"];
  const queueDepth = event.payload["queue_depth"];
  return {
    event: event.event_type,
    from_status: null,
    to_status: status,
    occurred_at: event.occurred_at,
    reason: typeof reason === "string" ? reason : null,
    queue_depth: typeof queueDepth === "number" ? queueDepth : null,
  };
}

const ROLLING_RATE_WINDOW_MS = 60_000;

/** A live approximation of "orders/min" from what the board has actually
 * seen in the last rolling minute — not the Prometheus counter Phase 9
 * would expose, but a real, honestly-labelled number rather than a
 * fabricated one. */
export function ordersPerMinute(orders: BoardOrder[], nowMs: number): number {
  return orders.filter((order) => nowMs - order.placedAt <= ROLLING_RATE_WINDOW_MS).length;
}

function isTerminalStatus(status: OrderStatus): boolean {
  return status === "delivered" || status === "rejected" || status === "failed";
}

/** Share of currently in-flight orders flagged `late` (SPEC.md §2's derived
 * boolean) — an approximation of Phase 9's `promise_error_seconds` p95
 * histogram, computed client-side from what the board already has rather
 * than a metric this phase doesn't build. `undefined` (not 0) when there's
 * nothing in flight to judge, so the status bar shows "no data" rather than
 * a misleading "0% late". */
export function lateRatioPercent(orders: BoardOrder[]): number | undefined {
  const inFlight = orders.filter((order) => !isTerminalStatus(order.status));
  if (inFlight.length === 0) return undefined;
  const late = inFlight.filter((order) => order.late).length;
  return Math.round((late / inFlight.length) * 100);
}

function slotProgress(claimedAt: string | null, freesAt: string | null, nowMs: number): number {
  if (!claimedAt || !freesAt) return 0;
  const start = new Date(claimedAt).getTime();
  const end = new Date(freesAt).getTime();
  if (end <= start) return 100;
  return Math.min(100, Math.max(0, ((nowMs - start) / (end - start)) * 100));
}

export function mapOvens(ovens: KitchenOvenRaw[] | null, nowMs: number): OvenViewModel[] {
  if (!ovens) return [];
  return ovens.map((oven) => ({
    id: oven.id,
    name: oven.name,
    slots: oven.slots.map((slot): { status: OvenSlotStatus; progress?: number } => {
      if (oven.status === "down") return { status: "down" };
      if (!slot.order_id) return { status: "free" };
      return { status: "occupied", progress: slotProgress(slot.claimed_at, slot.frees_at, nowMs) };
    }),
  }));
}

const COURIER_STATUS: Record<string, CourierStatus> = {
  offline: "offline",
  idle: "idle",
  assigned: "active",
  delivering: "active",
};

/** Couriers that have never reported a position (`x`/`y` both `null`, per
 * `dispatch.geo`'s "absent, not zero" contract) are excluded from the map —
 * there's nowhere honest to place a dot for them. */
export function mapCouriers(couriers: DispatchCourierRaw[] | null): CourierMapEntry[] {
  if (!couriers) return [];
  return couriers
    .filter(
      (courier): courier is DispatchCourierRaw & { x: number; y: number } =>
        courier.x !== null && courier.y !== null,
    )
    .map((courier) => ({
      id: courier.id,
      name: courier.name,
      status: COURIER_STATUS[courier.status] ?? "idle",
      x: courier.x,
      y: courier.y,
    }));
}

/** Trips still in flight (`assigned`/`picked_up`/`delivering` — dispatch's
 * own `GET /trips` already filters to these) drawn as a pickup->dropoff
 * line, so "N active trips" has something on the map explaining it rather
 * than a count next to unconnected courier dots. */
export function mapTripLines(
  trips: DispatchTripRaw[] | null,
): { id: string; code: string; fromX: number; fromY: number; toX: number; toY: number }[] {
  if (!trips) return [];
  return trips.map((trip) => ({
    id: trip.id,
    code: trip.code,
    fromX: trip.pickup_x,
    fromY: trip.pickup_y,
    toX: trip.dropoff_x,
    toY: trip.dropoff_y,
  }));
}

/** Every courier (unlike `mapCouriers`, which drops anyone with no reported
 * position — the roster has nothing to place on a map, so there's no reason
 * to hide an idle courier here) paired with their trips, grouped in
 * assignment order. Dispatch's `GET /trips` already sorts by `assigned_at`,
 * so grouping by `courier_id` via a plain filter preserves that order
 * without this function re-sorting anything itself. */
export function mapCourierRoster(
  couriers: DispatchCourierRaw[] | null,
  trips: DispatchTripRaw[] | null,
): CourierRosterEntry[] {
  if (!couriers) return [];
  const allTrips = trips ?? [];
  return couriers.map((courier) => ({
    id: courier.id,
    name: courier.name,
    status: COURIER_STATUS[courier.status] ?? "idle",
    trips: allTrips
      .filter((trip) => trip.courier_id === courier.id)
      .map((trip) => ({
        id: trip.id,
        code: trip.code,
        etaAtMs: new Date(trip.eta_at).getTime(),
      })),
  }));
}

/** `null` means dispatch didn't answer this field at all — kept distinct
 * from a confirmed `{ready_count: 0, ...}` all the way through so the board
 * never shows "no backlog" when it actually just couldn't ask. */
export function mapBacklogSummary(
  backlog: DispatchBacklogRaw | null | undefined,
): BacklogSummary | null {
  if (!backlog) return null;
  return {
    readyCount: backlog.ready_count,
    oldestWaitingSeconds: backlog.oldest_waiting_seconds,
  };
}
