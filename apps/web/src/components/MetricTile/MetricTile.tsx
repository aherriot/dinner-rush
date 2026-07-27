import styles from "./MetricTile.module.css";

export interface MetricTileProps {
  label: string;
  value?: string | number;
  delta?: { value: string; direction: "up" | "down" };
  stale?: boolean;
}

export function MetricTile({ label, value, delta, stale = false }: MetricTileProps) {
  const noData = value === undefined;
  return (
    <div className={styles.tile}>
      <span className={styles.label}>{label}</span>
      <div className={styles.row}>
        <span className={styles.value} data-stale={stale || undefined} data-no-data={noData || undefined}>
          {noData ? "—" : value}
        </span>
        {delta && !noData && (
          <span className={styles.delta} data-direction={delta.direction}>
            {delta.direction === "up" ? "▲" : "▼"} {delta.value}
          </span>
        )}
        {stale && !noData && <span className={styles["stale-badge"]}>stale</span>}
      </div>
    </div>
  );
}
