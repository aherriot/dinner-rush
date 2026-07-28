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

export interface DispatchPanelProps {
  couriers?: CourierMapEntry[];
  activeTripCount?: number;
  /** The abstract city grid's width/height (DESIGN.md §10) — 100 by default. */
  gridSize?: number;
  state?: PanelState;
  errorMessage?: string;
}

/**
 * The board's DISPATCH panel (PIZZA.md's demo mockup, 380px column) — a
 * stylised city-grid map, no tile server or network dependency (PHASES.md
 * Phase 7). Courier positions come from the abstract 100x100 grid
 * (SPEC.md §1.3) and are placed by percentage, not pixels, so the map
 * reflows with the panel rather than needing a fixed canvas size.
 */
export function DispatchPanel({
  couriers = [],
  activeTripCount,
  gridSize = 100,
  state = "idle",
  errorMessage,
}: DispatchPanelProps) {
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
          aria-label={`Dispatch map: ${couriers.length} courier${couriers.length === 1 ? "" : "s"} online`}
        >
          {couriers.map((courier) => (
            <div
              key={courier.id}
              className={styles.pin}
              style={{
                left: `${(courier.x / gridSize) * 100}%`,
                top: `${(courier.y / gridSize) * 100}%`,
              }}
            >
              <CourierDot status={courier.status} selected={courier.selected} name={courier.name} />
            </div>
          ))}
        </div>
      </div>
    </Panel>
  );
}
