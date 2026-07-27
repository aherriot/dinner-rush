import styles from "./Meter.module.css";

export type MeterStatus = "normal" | "at-capacity" | "over-capacity" | "down";

export interface MeterProps {
  label: string;
  value: number;
  status?: MeterStatus;
}

export function Meter({ label, value, status = "normal" }: MeterProps) {
  const clamped = Math.min(100, Math.max(0, value));
  return (
    <div className={styles.wrapper}>
      <div className={styles.header}>
        <span>{label}</span>
        <span className={styles.value}>{status === "down" ? "down" : `${Math.round(value)}%`}</span>
      </div>
      {status === "down" ? (
        <div className={styles.track} data-status={status} role="img" aria-label={`${label}: out of service`} />
      ) : (
        <div
          className={styles.track}
          data-status={status}
          role="meter"
          aria-label={label}
          aria-valuenow={value}
          aria-valuemin={0}
          aria-valuemax={100}
        >
          <div className={styles.fill} style={{ width: `${clamped}%` }} />
        </div>
      )}
    </div>
  );
}
