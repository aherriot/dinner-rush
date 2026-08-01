import { useEffect, useState } from "react";
import { MetricTile } from "../MetricTile/MetricTile";
import { ActionMenu, SegmentedControl, Toolbar } from "../Toolbar/Toolbar";
import styles from "./StatusBar.module.css";

export type SpeedValue = 1 | 10 | 60;

const SPEED_LABELS: Record<SpeedValue, string> = { 1: "1x", 10: "10x", 60: "60x" };
const SPEED_OPTIONS = (Object.keys(SPEED_LABELS) as unknown as SpeedValue[]).map((speed) => ({
  value: String(speed),
  label: SPEED_LABELS[speed],
}));

export interface ChaosScenarioOption {
  name: string;
  label: string;
}

export interface StatusBarProps {
  speed: SpeedValue;
  onSpeedChange: (speed: SpeedValue) => void;
  ordersPerMinute?: number;
  p95LatePercent?: number;
  /** `sum(stream_pending)` (SPEC.md §7, Phase 9) — the backlog a chaos demo
   * drains, pushed from Prometheus over the board socket every ~5s rather
   * than computed client-side, unlike `ordersPerMinute`/`p95LatePercent`. */
  streamPending?: number;
  /** p95 of `promise_error_seconds` (Phase 9) — signed seconds, `delivered_at`
   * minus `promised_at`; positive means late. The falsifiable sibling of the
   * client-approximated `p95LatePercent` tile. */
  promiseErrorP95Seconds?: number;
  scenarios: ChaosScenarioOption[];
  activeScenarios?: string[];
  onStartScenario: (name: string) => void;
  onStopScenario: (name: string) => void;
  connected?: boolean;
}

function formatSignedSeconds(seconds: number): string {
  const rounded = Math.round(seconds);
  return rounded > 0 ? `+${rounded}s` : `${rounded}s`;
}

function useClock(): string {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const timer = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);
  return now.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

/**
 * The board's status bar (DESIGN.md §10 — 56px row: clock, speed, rate,
 * p95, chaos). Chaos is a `Toolbar` `ActionMenu` per DESIGN.md §7's own
 * example ("Menu (overflow actions, e.g. chaos scenarios)"), not inline
 * buttons — active scenarios surface as dismissible chips next to it so
 * stopping one doesn't require remembering which menu item started it.
 */
export function StatusBar({
  speed,
  onSpeedChange,
  ordersPerMinute,
  p95LatePercent,
  streamPending,
  promiseErrorP95Seconds,
  scenarios,
  activeScenarios = [],
  onStartScenario,
  onStopScenario,
  connected = true,
}: StatusBarProps) {
  const clock = useClock();

  return (
    <div className={styles.bar}>
      <div className={styles.section}>
        <span className={styles.clock} data-testid="board-clock">
          {clock}
        </span>
        <span
          className={styles["connection-dot"]}
          data-connected={connected || undefined}
          role="img"
          aria-label={connected ? "Live" : "Reconnecting"}
        />
      </div>

      <div className={styles.section}>
        <Toolbar>
          <SegmentedControl
            label="Speed"
            options={SPEED_OPTIONS}
            value={String(speed)}
            onChange={(value) => onSpeedChange(Number(value) as SpeedValue)}
          />
        </Toolbar>
      </div>

      <div className={styles.section}>
        <MetricTile label="Rate" value={ordersPerMinute !== undefined ? `${ordersPerMinute}/min` : undefined} />
        <MetricTile
          label="p95 late"
          value={p95LatePercent !== undefined ? `${p95LatePercent}%` : undefined}
        />
        <MetricTile
          label="Backlog"
          value={streamPending !== undefined ? String(streamPending) : undefined}
        />
        <MetricTile
          label="Promise p95"
          value={
            promiseErrorP95Seconds !== undefined
              ? formatSignedSeconds(promiseErrorP95Seconds)
              : undefined
          }
        />
      </div>

      <div className={`${styles.section} ${styles.chaos}`}>
        {activeScenarios.map((name) => {
          const option = scenarios.find((scenario) => scenario.name === name);
          return (
            <button
              key={name}
              type="button"
              className={styles["active-chip"]}
              onClick={() => onStopScenario(name)}
            >
              {option?.label ?? name}
              <span aria-hidden="true"> ✕</span>
            </button>
          );
        })}
        <ActionMenu
          label="Chaos"
          placement="top"
          align="end"
          items={scenarios.map((scenario) => ({
            key: scenario.name,
            label: scenario.label,
            onSelect: () => onStartScenario(scenario.name),
          }))}
        />
      </div>
    </div>
  );
}
