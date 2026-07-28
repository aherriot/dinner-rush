import { CourierDot, type CourierStatus } from "../CourierDot/CourierDot";
import { MetricTile } from "../MetricTile/MetricTile";
import { Panel, type PanelState } from "../Panel/Panel";
import styles from "./DispatchPanel.module.css";

export interface CourierMapEntry {
  id: string;
  name?: string;
  status: CourierStatus;
  x: number;
  y: number;
  selected?: boolean;
}

export interface TripLine {
  id: string;
  code: string;
  fromX: number;
  fromY: number;
  toX: number;
  toY: number;
}

export interface GridPoint {
  x: number;
  y: number;
}

const LEGEND: { status: CourierStatus; label: string }[] = [
  { status: "idle", label: "Idle" },
  { status: "active", label: "Active" },
  { status: "offline", label: "Offline" },
];

export interface DispatchPanelProps {
  couriers?: CourierMapEntry[];
  trips?: TripLine[];
  activeTripCount?: number;
  /** The abstract city grid's width/height (DESIGN.md §10) — 100 by default. */
  gridSize?: number;
  /** The fixed pickup point every trip line originates near — defaults to
   * the grid's centre, matching `config.example.yaml`'s `dispatch.
   * restaurant: {x: 50, y: 50}` for the default 100x100 grid. */
  restaurant?: GridPoint;
  state?: PanelState;
  errorMessage?: string;
}

function toPercent(value: number, gridSize: number): string {
  return `${(value / gridSize) * 100}%`;
}

/**
 * The board's DISPATCH panel (PIZZA.md's demo mockup, 380px column) — a
 * stylised city-grid map, no tile server or network dependency (PHASES.md
 * Phase 7). A restaurant marker anchors the grid, trip lines connect it to
 * each in-flight dropoff so "N active trips" has something legible to point
 * at, and a legend spells out what each courier colour means — a bare
 * scatter of same-size dots with no key is not information, however
 * accurate its positions are.
 */
export function DispatchPanel({
  couriers = [],
  trips = [],
  activeTripCount,
  gridSize = 100,
  restaurant,
  state = "idle",
  errorMessage,
}: DispatchPanelProps) {
  const origin = restaurant ?? { x: gridSize / 2, y: gridSize / 2 };

  return (
    <Panel
      title="Dispatch"
      state={couriers.length === 0 && state === "idle" ? "empty" : state}
      errorMessage={errorMessage}
      emptyMessage="No couriers online."
    >
      <div className={styles.body}>
        <MetricTile label="Active trips" value={activeTripCount} />
        <div
          className={styles.map}
          role="img"
          aria-label={`Dispatch map: ${couriers.length} courier${couriers.length === 1 ? "" : "s"} online, ${trips.length} trip${trips.length === 1 ? "" : "s"} in progress`}
        >
          <svg
            className={styles.overlay}
            viewBox={`0 0 ${gridSize} ${gridSize}`}
            preserveAspectRatio="none"
            aria-hidden="true"
          >
            {trips.map((trip) => (
              <line
                key={trip.id}
                x1={origin.x}
                y1={origin.y}
                x2={trip.toX}
                y2={trip.toY}
                className={styles["trip-line"]}
                strokeWidth={0.4}
                opacity={0.5}
              />
            ))}
            <rect
              x={origin.x - 1.5}
              y={origin.y - 1.5}
              width={3}
              height={3}
              className={styles.restaurant}
            />
          </svg>
          {couriers.map((courier) => (
            <div
              key={courier.id}
              className={styles.pin}
              style={{ left: toPercent(courier.x, gridSize), top: toPercent(courier.y, gridSize) }}
            >
              <CourierDot status={courier.status} selected={courier.selected} name={courier.name} />
            </div>
          ))}
        </div>
        <ul className={styles.legend}>
          {LEGEND.map(({ status, label }) => (
            <li key={status} className={styles["legend-item"]}>
              {/* Decorative — the adjacent text label is what's exposed to
                  assistive tech; without this, two same-status dots (a real
                  courier plus its legend swatch) would collide as
                  ambiguous matches for anything querying by role+name. */}
              <span aria-hidden="true">
                <CourierDot status={status} />
              </span>
              <span>{label}</span>
            </li>
          ))}
          <li className={styles["legend-item"]}>
            <span className={styles["legend-restaurant"]} aria-hidden="true" />
            <span>Restaurant</span>
          </li>
        </ul>
      </div>
    </Panel>
  );
}
