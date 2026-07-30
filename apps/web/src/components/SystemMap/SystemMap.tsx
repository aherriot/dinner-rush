import { useEffect, useState, type KeyboardEvent } from "react";
import { DatabaseSchemaModal } from "../DatabaseSchemaModal/DatabaseSchemaModal";
import { Panel } from "../Panel/Panel";
import { RedisTopologyModal } from "../RedisTopologyModal/RedisTopologyModal";
import { REDIS_TOPOLOGY, SCHEMA_BY_NODE_ID } from "./schemaData";
import type { ActivePulse } from "./useSystemMapPulses";
import {
  PULSE_STAGE_MS,
  SYSTEM_EDGES,
  SYSTEM_NODES,
  type EdgeDef,
  type NodeId,
  type ServiceHealth,
} from "./systemMapState";
import styles from "./SystemMap.module.css";

export interface SystemMapProps {
  health: Record<NodeId, ServiceHealth>;
  /** One short line of real state per node, beyond health — orders/min,
   * oven occupancy, active trips, and so on (`systemMapState.
   * computeNodeMetrics`). Absent for a node this render has no data for
   * yet, rendered as nothing rather than a placeholder. Not used by the
   * database nodes or Redis — they list their real tables/streams/groups
   * directly instead of a summarising count. */
  metrics?: Partial<Record<NodeId, string>>;
  pulses?: ActivePulse[];
  loading?: boolean;
}

interface Point {
  x: number;
  y: number;
}

const SERVICE_WIDTH = 160;
const SERVICE_HEIGHT = 74;
const DB_WIDTH = 210;

/** Every node lists its real content directly (table names; stream and
 * group names) rather than hiding it behind a hover tooltip — a box grows
 * to fit exactly as many lines as it has real items, nothing is truncated
 * or invented to keep a uniform height. */
const LIST_START_Y = 50;
const LIST_LINE_HEIGHT = 12;
const LIST_BOTTOM_PADDING = 8;

function heightForListLines(lineCount: number): number {
  return LIST_START_Y + lineCount * LIST_LINE_HEIGHT + LIST_BOTTOM_PADDING;
}

/** Stable, de-duplicated order of every consumer group across all three
 * streams — first-appearance order, not alphabetical, so it reads
 * `cg:kitchen, cg:dispatch, cg:analytics, ...` the same order the topology
 * modal's `events:order` section lists them in. */
const REDIS_DISTINCT_GROUPS = Array.from(
  new Set(REDIS_TOPOLOGY.flatMap((entry) => entry.groups.map((g) => g.group))),
);

const FRONT_OF_HOUSE_DB_HEIGHT = heightForListLines(SCHEMA_BY_NODE_ID["front-of-house-db"]?.length ?? 0);
const KITCHEN_DB_HEIGHT = heightForListLines(SCHEMA_BY_NODE_ID["kitchen-db"]?.length ?? 0);
const DISPATCH_DB_HEIGHT = heightForListLines(SCHEMA_BY_NODE_ID["dispatch-db"]?.length ?? 0);
// "Streams (N):" header + one line per stream + "Groups (N):" header + one
// line per distinct group.
const REDIS_HEIGHT = heightForListLines(2 + REDIS_TOPOLOGY.length + REDIS_DISTINCT_GROUPS.length);

/** Fixed layout, not force-directed — DESIGN.md's "dense, deterministic
 * instrumentation" doctrine applies to node position the same way it
 * applies to numbers: nothing on this board should jitter between renders.
 * Three independent column stacks (left/mid/right), top-anchored: each
 * node's own real content height determines how much room it needs, and
 * neighbouring columns are never affected by one column's taller node
 * (front-of-house-db and Redis both list a lot; Simulator/Browser/Kitchen/Dispatch
 * don't, and shouldn't be stretched to match). */
const COL_X = { left: 120, mid: 440, right: 760 };

const TOP_MARGIN = 30;
const FRONT_OF_HOUSE_DB_TOP = TOP_MARGIN;
const ROW1_TOP = FRONT_OF_HOUSE_DB_TOP + FRONT_OF_HOUSE_DB_HEIGHT + 30;
const ROW1_BOTTOM = ROW1_TOP + SERVICE_HEIGHT;
// Clearance for the "capacity quote" / "events:order" / "board reads" edge
// labels between the two service rows.
const ROW2_TOP = ROW1_BOTTOM + 110;
const ROW2_BOTTOM = ROW2_TOP + SERVICE_HEIGHT;
const DB_ROW2_TOP = ROW2_BOTTOM + 30;

const NODE_TOP: Record<NodeId, number> = {
  "front-of-house-db": FRONT_OF_HOUSE_DB_TOP,
  simulator: ROW1_TOP,
  "front-of-house": ROW1_TOP,
  browser: ROW1_TOP,
  kitchen: ROW2_TOP,
  redis: ROW2_TOP,
  dispatch: ROW2_TOP,
  "kitchen-db": DB_ROW2_TOP,
  "dispatch-db": DB_ROW2_TOP,
};

const NODE_HEIGHT: Record<NodeId, number> = {
  "front-of-house-db": FRONT_OF_HOUSE_DB_HEIGHT,
  simulator: SERVICE_HEIGHT,
  "front-of-house": SERVICE_HEIGHT,
  browser: SERVICE_HEIGHT,
  kitchen: SERVICE_HEIGHT,
  redis: REDIS_HEIGHT,
  dispatch: SERVICE_HEIGHT,
  "kitchen-db": KITCHEN_DB_HEIGHT,
  "dispatch-db": DISPATCH_DB_HEIGHT,
};

const NODE_WIDTH: Record<NodeId, number> = {
  "front-of-house-db": DB_WIDTH,
  simulator: SERVICE_WIDTH,
  "front-of-house": SERVICE_WIDTH,
  browser: SERVICE_WIDTH,
  kitchen: SERVICE_WIDTH,
  redis: SERVICE_WIDTH,
  dispatch: SERVICE_WIDTH,
  "kitchen-db": DB_WIDTH,
  "dispatch-db": DB_WIDTH,
};

/** Edges connect to each node's centre point — its box, drawn afterwards
 * and opaque, covers the segment nearest it, so the exact centre (not the
 * top-anchored box origin) is what `EdgeLine` needs. */
const NODE_CENTER: Record<NodeId, Point> = Object.fromEntries(
  (Object.keys(NODE_TOP) as NodeId[]).map((id) => {
    const x = id === "simulator" || id === "kitchen" || id === "kitchen-db"
      ? COL_X.left
      : id === "browser" || id === "dispatch" || id === "dispatch-db"
        ? COL_X.right
        : COL_X.mid;
    return [id, { x, y: NODE_TOP[id] + NODE_HEIGHT[id] / 2 }];
  }),
) as Record<NodeId, Point>;

const VIEW_WIDTH = COL_X.right + DB_WIDTH / 2 + 20;
const VIEW_HEIGHT =
  Math.max(ROW2_TOP + REDIS_HEIGHT, DB_ROW2_TOP + Math.max(KITCHEN_DB_HEIGHT, DISPATCH_DB_HEIGHT)) +
  TOP_MARGIN;

/** Front-of-house and the browser have two edges between them (an HTTP leg and a
 * websocket leg, `systemMapState.SYSTEM_EDGES`) — without an offset they'd
 * draw as one line with two labels stacked illegibly on top of each other.
 * A small perpendicular nudge, applied to that one node pair only, turns
 * them into two parallel lines with their own label rows. */
const EDGE_OFFSET: Partial<Record<EdgeDef["id"], number>> = {
  "browser-front-of-house-http": -8,
  "browser-front-of-house-ws": 8,
};

/** SMIL `<animate dur>` can't read the CSS custom property this ~matches
 * (`--dur-slow`, DESIGN.md §6) — see `PULSE_STAGE_MS`'s own comment. */
const PULSE_DUR = `${PULSE_STAGE_MS / 1000}s`;

const HEALTH_META: Record<ServiceHealth, { glyph: string; label: string }> = {
  healthy: { glyph: "✓", label: "Healthy" },
  degraded: { glyph: "△", label: "Degraded" },
  down: { glyph: "✕", label: "Down" },
  unknown: { glyph: "?", label: "Unknown" },
};

/** Per-node copy for states whose generic label would mislead — an idle
 * simulator isn't "unknown" as a problem, and a websocket-down front-of-house
 * isn't fully "degraded" in the alarming sense, it's the exact fallback
 * DECISIONS.md §0003 describes (REST polling picks up the slack). */
const LABEL_OVERRIDES: Partial<Record<NodeId, Partial<Record<ServiceHealth, string>>>> = {
  simulator: { healthy: "Sending load", unknown: "Idle" },
  browser: { degraded: "Reconnecting" },
  "front-of-house": { degraded: "Polling REST" },
  redis: { degraded: "No signal" },
};

function healthLabelFor(nodeId: NodeId, health: ServiceHealth): string {
  return LABEL_OVERRIDES[nodeId]?.[health] ?? HEALTH_META[health].label;
}

function useReducedMotion(): boolean {
  const [reduced, setReduced] = useState(
    () => typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches,
  );
  useEffect(() => {
    const query = window.matchMedia("(prefers-reduced-motion: reduce)");
    const listener = () => setReduced(query.matches);
    query.addEventListener("change", listener);
    return () => query.removeEventListener("change", listener);
  }, []);
  return reduced;
}

function EdgeLine({
  edge,
  active,
  reducedMotion,
}: {
  edge: EdgeDef;
  active: boolean;
  reducedMotion: boolean;
}) {
  const offset = EDGE_OFFSET[edge.id] ?? 0;
  const from = { ...NODE_CENTER[edge.from], y: NODE_CENTER[edge.from].y + offset };
  const to = { ...NODE_CENTER[edge.to], y: NODE_CENTER[edge.to].y + offset };
  const midX = (from.x + to.x) / 2;
  const midY = (from.y + to.y) / 2;
  const hasLabel = edge.label.length > 0;

  return (
    <g>
      <line
        x1={from.x}
        y1={from.y}
        x2={to.x}
        y2={to.y}
        strokeWidth={edge.kind === "event" ? 2 : edge.kind === "db" ? 1 : 1.25}
        strokeDasharray={edge.kind === "ws" ? "4 3" : edge.kind === "db" ? "1 3" : undefined}
        className={styles.edge}
        data-kind={edge.kind}
        data-flash={reducedMotion && active && edge.kind !== "db" ? "" : undefined}
      >
        {hasLabel && <title>{edge.label}</title>}
      </line>
      {hasLabel && (
        <>
          <rect
            x={midX - edge.label.length * 2.6}
            y={midY - 7}
            width={edge.label.length * 5.2}
            height={11}
            className={styles["edge-label-backing"]}
          />
          <text x={midX} y={midY + 3} textAnchor="middle" className={styles["edge-label"]}>
            {edge.label}
          </text>
        </>
      )}
      {/* "db" edges are structural ownership, never traffic — guarded here
          too, not just by nothing in systemMapState.ts ever producing a
          pulse for one. */}
      {!reducedMotion && active && edge.kind !== "db" && (
        <circle r={3.5} className={styles.pulse} data-kind={edge.kind}>
          <animate attributeName="cx" values={`${from.x};${to.x}`} dur={PULSE_DUR} fill="freeze" />
          <animate attributeName="cy" values={`${from.y};${to.y}`} dur={PULSE_DUR} fill="freeze" />
          <animate
            attributeName="opacity"
            values="0;1;1;0"
            keyTimes="0;0.15;0.75;1"
            dur={PULSE_DUR}
            fill="freeze"
          />
        </circle>
      )}
    </g>
  );
}

function handleActivationKey(event: KeyboardEvent, onOpen: () => void): void {
  if (event.key === "Enter" || event.key === " ") {
    event.preventDefault();
    onOpen();
  }
}

function DatabaseNode({
  id,
  health,
  onOpen,
}: {
  id: NodeId;
  health: ServiceHealth;
  onOpen: () => void;
}) {
  const node = SYSTEM_NODES.find((n) => n.id === id);
  if (!node) return null;
  const width = NODE_WIDTH[id];
  const height = NODE_HEIGHT[id];
  const x = NODE_CENTER[id].x - width / 2;
  const y = NODE_TOP[id];
  const meta = HEALTH_META[health];
  const label = healthLabelFor(id, health);
  const tables = node.tables ?? [];

  return (
    <g
      transform={`translate(${x}, ${y})`}
      role="button"
      tabIndex={0}
      aria-label={`${node.label} database — ${tables.length} tables. Open entity relationships.`}
      className={styles.clickable}
      onClick={onOpen}
      onKeyDown={(event) => handleActivationKey(event, onOpen)}
    >
      <title>
        {node.sublabel} — {node.detail} {label}
      </title>
      <rect width={width} height={height} rx={4} className={styles["db-node"]} data-health={health} />
      <text x={9} y={13} className={styles["db-node-label"]}>
        {node.label}
      </text>
      <text x={9} y={24} className={styles["node-sublabel"]}>
        {node.sublabel}
      </text>
      <g transform="translate(9, 36)">
        <text className={styles["health-glyph"]} data-health={health} aria-hidden="true">
          {meta.glyph}
        </text>
        <text x={12} y={0} className={styles["health-label"]} data-health={health}>
          {label}
        </text>
      </g>
      {tables.map((table, index) => (
        <text key={table} x={9} y={LIST_START_Y + index * LIST_LINE_HEIGHT} className={styles["list-item"]}>
          {table}
        </text>
      ))}
    </g>
  );
}

function RedisNode({ health, onOpen }: { health: ServiceHealth; onOpen: () => void }) {
  const node = SYSTEM_NODES.find((n) => n.id === "redis");
  if (!node) return null;
  const width = NODE_WIDTH.redis;
  const height = NODE_HEIGHT.redis;
  const x = NODE_CENTER.redis.x - width / 2;
  const y = NODE_TOP.redis;
  const meta = HEALTH_META[health];
  const label = healthLabelFor("redis", health);

  let line = 0;
  const streamsHeaderLine = line++;
  const streamLines = REDIS_TOPOLOGY.map(() => line++);
  const groupsHeaderLine = line++;
  const groupLines = REDIS_DISTINCT_GROUPS.map(() => line++);

  return (
    <g
      transform={`translate(${x}, ${y})`}
      role="button"
      tabIndex={0}
      aria-label={`Redis — ${REDIS_TOPOLOGY.length} streams, ${REDIS_DISTINCT_GROUPS.length} consumer groups. Open the full topology.`}
      className={styles.clickable}
      onClick={onOpen}
      onKeyDown={(event) => handleActivationKey(event, onOpen)}
    >
      <title>
        {node.label} — {node.detail} {label}
      </title>
      <rect width={width} height={height} rx={4} className={styles.node} data-health={health} />
      {/* Tighter header rhythm than the other service nodes (13/24/36,
          matching `DatabaseNode`) — Redis is the one service node with a
          list below its header, and `LIST_START_Y` (shared with
          `DatabaseNode`) needs the same clearance underneath it that
          `DatabaseNode`'s own header already proves works. */}
      <text x={10} y={13} className={styles["node-label"]}>
        {node.label}
      </text>
      <text x={10} y={24} className={styles["node-sublabel"]}>
        {node.sublabel}
      </text>
      <g transform="translate(10, 36)">
        <text className={styles["health-glyph"]} data-health={health} aria-hidden="true">
          {meta.glyph}
        </text>
        <text x={12} y={0} className={styles["health-label"]} data-health={health}>
          {label}
        </text>
      </g>
      <text x={10} y={LIST_START_Y + streamsHeaderLine * LIST_LINE_HEIGHT} className={styles["list-header"]}>
        Streams ({REDIS_TOPOLOGY.length}):
      </text>
      {REDIS_TOPOLOGY.map((entry, index) => (
        <text
          key={entry.stream}
          x={10}
          y={LIST_START_Y + streamLines[index] * LIST_LINE_HEIGHT}
          className={styles["list-item"]}
        >
          {entry.stream}
        </text>
      ))}
      <text x={10} y={LIST_START_Y + groupsHeaderLine * LIST_LINE_HEIGHT} className={styles["list-header"]}>
        Groups ({REDIS_DISTINCT_GROUPS.length}):
      </text>
      {REDIS_DISTINCT_GROUPS.map((group, index) => (
        <text
          key={group}
          x={10}
          y={LIST_START_Y + groupLines[index] * LIST_LINE_HEIGHT}
          className={styles["list-item"]}
        >
          {group}
        </text>
      ))}
    </g>
  );
}

function ServiceNode({
  id,
  health,
  metric,
}: {
  id: NodeId;
  health: ServiceHealth;
  metric?: string;
}) {
  const node = SYSTEM_NODES.find((n) => n.id === id);
  if (!node) return null;
  const width = NODE_WIDTH[id];
  const height = NODE_HEIGHT[id];
  const x = NODE_CENTER[id].x - width / 2;
  const y = NODE_TOP[id];
  const meta = HEALTH_META[health];
  const label = healthLabelFor(id, health);

  return (
    <g transform={`translate(${x}, ${y})`}>
      <title>
        {node.label} — {node.detail} {label}
        {metric ? ` — ${metric}` : ""}
      </title>
      <rect width={width} height={height} rx={4} className={styles.node} data-health={health} />
      <text x={10} y={18} className={styles["node-label"]}>
        {node.label}
      </text>
      <text x={10} y={31} className={styles["node-sublabel"]}>
        {node.sublabel}
      </text>
      {metric && (
        <text x={10} y={44} className={styles["node-metric"]}>
          {metric}
        </text>
      )}
      <g transform="translate(10, 58)">
        <text className={styles["health-glyph"]} data-health={health} aria-hidden="true">
          {meta.glyph}
        </text>
        <text x={12} y={0} className={styles["health-label"]} data-health={health}>
          {label}
        </text>
      </g>
    </g>
  );
}

const HEALTH_LEGEND: ServiceHealth[] = ["healthy", "degraded", "down", "unknown"];

/**
 * The board's live architecture diagram (a `System` view alongside the ops
 * board, `Board.tsx`) — every node's health is read from data the board
 * already holds (`systemMapState.computeNodeHealth`), every metric line is
 * reused from a number already computed elsewhere on the board
 * (`systemMapState.computeNodeMetrics`), and every travelling pulse replays
 * the real hop an event just took, derived from the event envelope's own
 * `producer` field rather than decoration (`systemMapState.
 * pulsePlanForEvent`). Every database and Redis lists its real tables/
 * streams/groups directly on the node, and clicking either opens a modal
 * with the fuller picture (`DatabaseSchemaModal`'s entity relationships,
 * `RedisTopologyModal`'s stream-by-stream consumer breakdown) — both
 * verified against the running stack in `schemaData.ts`, not invented.
 * There is deliberately no "empty" or full-panel "error" state here the way
 * `KitchenPanel`/`DispatchPanel` have one: an unreachable service is itself
 * one of the four things this diagram exists to show, not a reason to hide
 * it.
 */
export function SystemMap({ health, metrics = {}, pulses = [], loading = false }: SystemMapProps) {
  const reducedMotion = useReducedMotion();
  const activeEdgeIds = new Set(pulses.map((pulse) => pulse.edgeId));
  const [openNode, setOpenNode] = useState<NodeId | null>(null);

  const unhealthy = SYSTEM_NODES.filter((node) => health[node.id] !== "healthy");
  const summary =
    unhealthy.length === 0
      ? `System map: all ${SYSTEM_NODES.length} services healthy`
      : `System map: ${unhealthy
          .map((node) => {
            // A database node's label is its real Postgres DB name (e.g.
            // "kitchen"), same word as its owning service's — "DB" here
            // disambiguates the two in a flat list of unhealthy nodes.
            const name = node.kind === "database" ? `${node.label} DB` : node.label;
            return `${name} ${healthLabelFor(node.id, health[node.id])}`;
          })
          .join(", ")}`;

  const openSchema = openNode ? SCHEMA_BY_NODE_ID[openNode] : undefined;
  const openNodeDef = openNode ? SYSTEM_NODES.find((n) => n.id === openNode) : undefined;

  return (
    <Panel title="Live system map" state={loading ? "loading" : "idle"}>
      <div className={styles.body}>
        <svg
          viewBox={`0 0 ${VIEW_WIDTH} ${VIEW_HEIGHT}`}
          className={styles.diagram}
          // Not `role="img"` — ARIA treats an "img" as an atomic leaf with
          // no exposed descendants, which conflicts with the real
          // `role="button"` database/Redis nodes nested inside (axe's
          // nested-interactive rule catches exactly this). "group" allows
          // both: an overall accessible name via `aria-label` here, and
          // each interactive child exposing its own.
          role="group"
          aria-label={summary}
        >
          <g>
            {SYSTEM_EDGES.map((edge) => (
              <EdgeLine
                key={edge.id}
                edge={edge}
                active={activeEdgeIds.has(edge.id)}
                reducedMotion={reducedMotion}
              />
            ))}
          </g>
          <g>
            {SYSTEM_NODES.map((node) => {
              if (node.kind === "database") {
                return (
                  <DatabaseNode
                    key={node.id}
                    id={node.id}
                    health={health[node.id]}
                    onOpen={() => setOpenNode(node.id)}
                  />
                );
              }
              if (node.id === "redis") {
                return (
                  <RedisNode key="redis" health={health.redis} onOpen={() => setOpenNode("redis")} />
                );
              }
              return (
                <ServiceNode
                  key={node.id}
                  id={node.id}
                  health={health[node.id]}
                  metric={metrics[node.id]}
                />
              );
            })}
          </g>
        </svg>
        <ul className={styles.legend}>
          {HEALTH_LEGEND.map((state) => (
            <li key={state} className={styles["legend-item"]}>
              <span className={styles["legend-glyph"]} data-health={state} aria-hidden="true">
                {HEALTH_META[state].glyph}
              </span>
              <span>{HEALTH_META[state].label}</span>
            </li>
          ))}
          <li className={styles["legend-item"]}>
            <span className={styles["legend-line"]} data-kind="event" aria-hidden="true" />
            <span>Event stream</span>
          </li>
          <li className={styles["legend-item"]}>
            <span className={styles["legend-line"]} data-kind="http" aria-hidden="true" />
            <span>HTTP</span>
          </li>
          <li className={styles["legend-item"]}>
            <span className={styles["legend-line"]} data-kind="ws" aria-hidden="true" />
            <span>Websocket</span>
          </li>
          <li className={styles["legend-item"]}>
            <span className={styles["legend-line"]} data-kind="db" aria-hidden="true" />
            <span>Owns database</span>
          </li>
          <li className={styles["legend-item"]}>Click a database or Redis for details.</li>
        </ul>
      </div>
      {openSchema && openNodeDef && (
        <DatabaseSchemaModal
          open
          onClose={() => setOpenNode(null)}
          databaseName={openNodeDef.label}
          tables={openSchema}
        />
      )}
      <RedisTopologyModal open={openNode === "redis"} onClose={() => setOpenNode(null)} streams={REDIS_TOPOLOGY} />
    </Panel>
  );
}
