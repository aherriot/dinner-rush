import { MetricTile } from "../MetricTile/MetricTile";
import { OvenSlot, type OvenSlotProps } from "../OvenSlot/OvenSlot";
import { Panel, type PanelState } from "../Panel/Panel";
import styles from "./KitchenPanel.module.css";

export interface OvenViewModel {
  id: string;
  name: string;
  slots: OvenSlotProps[];
}

export interface KitchenPanelProps {
  ovens?: OvenViewModel[];
  queueDepth?: number;
  state?: PanelState;
  errorMessage?: string;
}

/**
 * Kitchen's oven occupancy + queue depth (PHASES.md Phase 4) — a board
 * panel built from Phase 1 primitives (`OvenSlot`, `MetricTile`, `Panel`).
 * Purely props-driven; wiring it to `GET /ovens` and `GET /queue` is
 * Phase 8's job when the board assembles every panel.
 */
export function KitchenPanel({
  ovens = [],
  queueDepth,
  state = "idle",
  errorMessage,
}: KitchenPanelProps) {
  return (
    <Panel
      title="Kitchen"
      state={ovens.length === 0 && state === "idle" ? "empty" : state}
      errorMessage={errorMessage}
      emptyMessage="No ovens configured."
    >
      <div className={styles.body}>
        <MetricTile label="Queue depth" value={queueDepth} />
        <div className={styles.ovens}>
          {ovens.map((oven) => (
            <div key={oven.id} className={styles.oven}>
              <span className={styles["oven-name"]}>{oven.name}</span>
              <div className={styles.slots}>
                {oven.slots.map((slot, index) => (
                  <OvenSlot key={index} {...slot} />
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
    </Panel>
  );
}
