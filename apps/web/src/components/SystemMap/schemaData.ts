/**
 * Real per-database schema — every table and column verified directly
 * against the running databases (`\d <table>` against `front_of_house`/`kitchen`/
 * `dispatch`, 2026-07-30), not reconstructed from ORM naming conventions.
 * Feeds the system map's "entity relationship" modal — the on-canvas node
 * only lists table names (`systemMapState.ts`'s `NodeDef.tables`); this is
 * the fuller detail behind a click.
 */

import type { NodeId } from "./systemMapState";

export interface SchemaColumn {
  name: string;
  type: string;
  primaryKey?: boolean;
  /** `"table.column"` this column is a foreign key into. */
  references?: string;
}

export interface SchemaTable {
  name: string;
  columns: SchemaColumn[];
}

export const FRONT_OF_HOUSE_SCHEMA: SchemaTable[] = [
  {
    name: "accounts_staff",
    columns: [
      { name: "id", type: "uuid", primaryKey: true },
      { name: "name", type: "varchar(100)" },
      { name: "role", type: "varchar(10)" },
      { name: "user_id", type: "integer", references: "auth_user.id" },
    ],
  },
  {
    name: "catalog_menuitem",
    columns: [
      { name: "id", type: "uuid", primaryKey: true },
      { name: "sku", type: "varchar(20)" },
      { name: "name", type: "varchar(100)" },
      { name: "description", type: "text" },
      { name: "base_price_cents", type: "integer" },
      { name: "prep_seconds", type: "integer" },
      { name: "bake_seconds", type: "integer" },
      { name: "oven_slots", type: "smallint" },
      { name: "station", type: "varchar(10)" },
      { name: "available", type: "boolean" },
      { name: "sort_order", type: "smallint" },
    ],
  },
  {
    name: "customers_customer",
    columns: [
      { name: "id", type: "uuid", primaryKey: true },
      { name: "name", type: "varchar(100)" },
      { name: "email", type: "varchar(254)" },
      { name: "phone", type: "varchar(30)" },
      { name: "created_at", type: "timestamptz" },
    ],
  },
  {
    name: "customers_address",
    columns: [
      { name: "id", type: "uuid", primaryKey: true },
      { name: "label", type: "varchar(50)" },
      { name: "line1", type: "varchar(200)" },
      { name: "grid_x", type: "smallint" },
      { name: "grid_y", type: "smallint" },
      { name: "notes", type: "varchar(200)" },
      { name: "customer_id", type: "uuid", references: "customers_customer.id" },
    ],
  },
  {
    name: "orders_order",
    columns: [
      { name: "id", type: "uuid", primaryKey: true },
      { name: "code", type: "varchar(20)" },
      { name: "status", type: "varchar(20)" },
      { name: "subtotal_cents", type: "integer" },
      { name: "delivery_fee_cents", type: "integer" },
      { name: "total_cents", type: "integer" },
      { name: "placed_at", type: "timestamptz" },
      { name: "accepted_at", type: "timestamptz?" },
      { name: "promised_at", type: "timestamptz?" },
      { name: "ready_at", type: "timestamptz?" },
      { name: "delivered_at", type: "timestamptz?" },
      { name: "rejection_reason", type: "varchar(20)?" },
      { name: "idempotency_key", type: "varchar(100)?" },
      { name: "address_id", type: "uuid", references: "customers_address.id" },
      { name: "customer_id", type: "uuid", references: "customers_customer.id" },
    ],
  },
  {
    name: "orders_orderitem",
    columns: [
      { name: "id", type: "uuid", primaryKey: true },
      { name: "qty", type: "smallint" },
      { name: "unit_price_cents", type: "integer" },
      { name: "name_snapshot", type: "varchar(100)" },
      { name: "prep_seconds_snapshot", type: "integer" },
      { name: "bake_seconds_snapshot", type: "integer" },
      { name: "menu_item_id", type: "uuid", references: "catalog_menuitem.id" },
      { name: "order_id", type: "uuid", references: "orders_order.id" },
    ],
  },
  {
    name: "orders_orderstatusevent",
    columns: [
      { name: "id", type: "uuid", primaryKey: true },
      { name: "from_status", type: "varchar(20)?" },
      { name: "to_status", type: "varchar(20)" },
      { name: "event", type: "varchar(20)" },
      { name: "occurred_at", type: "timestamptz" },
      { name: "order_id", type: "uuid", references: "orders_order.id" },
      { name: "queue_depth", type: "integer?" },
      { name: "reason", type: "varchar(20)?" },
    ],
  },
  {
    name: "orders_ordercodesequence",
    columns: [{ name: "id", type: "bigint", primaryKey: true }],
  },
  {
    name: "eventing_eventtypecounter",
    columns: [
      { name: "id", type: "bigint", primaryKey: true },
      { name: "event_type", type: "varchar(100)" },
      { name: "count", type: "bigint" },
    ],
  },
  {
    name: "outbox",
    columns: [
      { name: "id", type: "bigint", primaryKey: true },
      { name: "event_id", type: "uuid" },
      { name: "stream", type: "varchar(100)" },
      { name: "envelope", type: "jsonb" },
      { name: "created_at", type: "timestamptz" },
      { name: "published_at", type: "timestamptz?" },
    ],
  },
  {
    name: "processed_event",
    columns: [
      { name: "id", type: "bigint", primaryKey: true },
      { name: "consumer_group", type: "varchar(100)" },
      { name: "event_id", type: "uuid" },
      { name: "processed_at", type: "timestamptz" },
    ],
  },
];

export const KITCHEN_SCHEMA: SchemaTable[] = [
  {
    name: "oven",
    columns: [
      { name: "id", type: "uuid", primaryKey: true },
      { name: "name", type: "varchar" },
      { name: "slot_count", type: "smallint" },
      { name: "status", type: "varchar" },
      { name: "event_sequence", type: "integer" },
    ],
  },
  {
    name: "oven_slot",
    columns: [
      { name: "id", type: "uuid", primaryKey: true },
      { name: "oven_id", type: "uuid", references: "oven.id" },
      { name: "slot_index", type: "smallint" },
      { name: "order_id", type: "uuid?" },
      { name: "claimed_at", type: "timestamptz?" },
      { name: "frees_at", type: "timestamptz?" },
    ],
  },
  {
    name: "station",
    columns: [
      { name: "id", type: "uuid", primaryKey: true },
      { name: "name", type: "varchar" },
      { name: "kind", type: "varchar" },
      { name: "capacity", type: "smallint" },
      { name: "status", type: "varchar" },
    ],
  },
  {
    name: "ticket",
    columns: [
      { name: "id", type: "uuid", primaryKey: true },
      { name: "order_id", type: "uuid" },
      { name: "code", type: "varchar" },
      { name: "status", type: "varchar" },
      { name: "items", type: "jsonb" },
      { name: "total_bake_seconds", type: "integer" },
      { name: "queued_at", type: "timestamptz" },
      { name: "started_at", type: "timestamptz?" },
      { name: "baked_at", type: "timestamptz?" },
      { name: "ready_at", type: "timestamptz?" },
      { name: "oven_slot_id", type: "uuid?", references: "oven_slot.id" },
      { name: "priority", type: "integer" },
    ],
  },
  {
    name: "outbox",
    columns: [
      { name: "id", type: "bigint", primaryKey: true },
      { name: "event_id", type: "uuid" },
      { name: "stream", type: "varchar" },
      { name: "envelope", type: "jsonb" },
      { name: "created_at", type: "timestamptz" },
      { name: "published_at", type: "timestamptz?" },
    ],
  },
  {
    name: "processed_event",
    columns: [
      { name: "id", type: "bigint", primaryKey: true },
      { name: "consumer_group", type: "varchar" },
      { name: "event_id", type: "uuid" },
      { name: "processed_at", type: "timestamptz" },
    ],
  },
];

export const DISPATCH_SCHEMA: SchemaTable[] = [
  {
    name: "courier",
    columns: [
      { name: "id", type: "uuid", primaryKey: true },
      { name: "name", type: "varchar" },
      { name: "status", type: "varchar" },
      { name: "vehicle", type: "varchar" },
      { name: "speed_cells_per_min", type: "numeric(6,2)" },
      { name: "shift_started_at", type: "timestamptz?" },
    ],
  },
  {
    name: "trip",
    columns: [
      { name: "id", type: "uuid", primaryKey: true },
      { name: "courier_id", type: "uuid", references: "courier.id" },
      { name: "order_id", type: "uuid" },
      { name: "code", type: "varchar" },
      { name: "status", type: "varchar" },
      { name: "pickup_x", type: "smallint" },
      { name: "pickup_y", type: "smallint" },
      { name: "dropoff_x", type: "smallint" },
      { name: "dropoff_y", type: "smallint" },
      { name: "assigned_at", type: "timestamptz" },
      { name: "picked_up_at", type: "timestamptz?" },
      { name: "delivered_at", type: "timestamptz?" },
      { name: "failed_at", type: "timestamptz?" },
      { name: "eta_at", type: "timestamptz" },
      { name: "distance_cells", type: "integer" },
      { name: "failure_reason", type: "varchar?" },
    ],
  },
  {
    name: "address_grant",
    columns: [
      { name: "id", type: "uuid", primaryKey: true },
      { name: "trip_id", type: "uuid", references: "trip.id" },
      { name: "courier_id", type: "uuid" },
      { name: "dropoff_x", type: "smallint" },
      { name: "dropoff_y", type: "smallint" },
      { name: "line1", type: "varchar" },
      { name: "granted_at", type: "timestamptz" },
      { name: "expires_at", type: "timestamptz" },
      { name: "revoked_at", type: "timestamptz?" },
    ],
  },
  {
    name: "pending_dropoff",
    columns: [
      { name: "order_id", type: "uuid", primaryKey: true },
      { name: "code", type: "varchar" },
      { name: "dropoff_x", type: "smallint" },
      { name: "dropoff_y", type: "smallint" },
      { name: "line1", type: "varchar" },
      { name: "created_at", type: "timestamptz" },
      { name: "ready_at", type: "timestamptz?" },
    ],
  },
  {
    name: "outbox",
    columns: [
      { name: "id", type: "bigint", primaryKey: true },
      { name: "event_id", type: "uuid" },
      { name: "stream", type: "varchar" },
      { name: "envelope", type: "jsonb" },
      { name: "created_at", type: "timestamptz" },
      { name: "published_at", type: "timestamptz?" },
    ],
  },
  {
    name: "processed_event",
    columns: [
      { name: "id", type: "bigint", primaryKey: true },
      { name: "consumer_group", type: "varchar" },
      { name: "event_id", type: "uuid" },
      { name: "processed_at", type: "timestamptz" },
    ],
  },
];

export const SCHEMA_BY_NODE_ID: Partial<Record<NodeId, SchemaTable[]>> = {
  "front-of-house-db": FRONT_OF_HOUSE_SCHEMA,
  "kitchen-db": KITCHEN_SCHEMA,
  "dispatch-db": DISPATCH_SCHEMA,
};

export interface StreamTopology {
  stream: string;
  groups: { group: string; does: string }[];
}

/** Verified live: `docker exec redis-1 redis-cli XINFO GROUPS <stream>` for
 * each of the three streams (2026-07-30) — 6 distinct group names, not the
 * 5 in DECISIONS.md's early planning doc, which predates `cg:order-sync`
 * and the `cg:ws-fanout`/`cg:ws-board-fanout` split. */
export const REDIS_TOPOLOGY: StreamTopology[] = [
  {
    stream: "events:order",
    groups: [
      { group: "cg:kitchen", does: "Builds a ticket from order.accepted (consumers.py)." },
      {
        group: "cg:dispatch",
        does: "Caches the dropoff on order.placed; triggers assignment on order.ready.",
      },
      { group: "cg:analytics", does: "Increments an EventTypeCounter row per event type." },
      {
        group: "cg:order-sync",
        does: "Mirrors kitchen/dispatch transitions back onto front-of-house's own Order.status.",
      },
      { group: "cg:ws-fanout", does: "Pushes to the per-order channel OrderTracker subscribes to." },
      { group: "cg:ws-board-fanout", does: "Pushes to the single \"board\" channel this board's own socket reads." },
    ],
  },
  {
    stream: "events:oven",
    groups: [
      { group: "cg:ws-board-fanout", does: "Pushes oven state changes to the board's socket." },
    ],
  },
  {
    stream: "events:courier",
    groups: [
      {
        group: "cg:order-sync",
        does: "Mirrors courier.assigned/order.picked_up/delivering/delivered/failed onto Order.status.",
      },
      { group: "cg:ws-board-fanout", does: "Pushes courier events to the board's socket." },
    ],
  },
];
