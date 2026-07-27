import styles from "./CourierDot.module.css";

export type CourierStatus = "idle" | "active" | "offline";

export interface CourierDotProps {
  status: CourierStatus;
  selected?: boolean;
  name?: string;
}

export function CourierDot({ status, selected = false, name }: CourierDotProps) {
  return (
    <span
      className={styles.dot}
      data-status={status}
      data-selected={selected || undefined}
      role="img"
      aria-label={`${name ? `${name} — ` : ""}courier ${status}${selected ? ", selected" : ""}`}
    />
  );
}
