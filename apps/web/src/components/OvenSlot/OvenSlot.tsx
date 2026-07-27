import styles from "./OvenSlot.module.css";

export type OvenSlotStatus = "free" | "reserved" | "occupied" | "down";

export interface OvenSlotProps {
  status: OvenSlotStatus;
  progress?: number;
  label?: string;
}

export function OvenSlot({ status, progress = 0, label }: OvenSlotProps) {
  const clamped = Math.min(100, Math.max(0, progress));
  return (
    <div className={styles.slot} data-status={status} role="img" aria-label={`Oven slot: ${status}${status === "occupied" ? `, ${clamped}% baked` : ""}`}>
      {status === "occupied" && <div className={styles.fill} style={{ height: `${clamped}%` }} />}
      {label && (
        <div className={styles.label}>
          <span>{label}</span>
        </div>
      )}
    </div>
  );
}
