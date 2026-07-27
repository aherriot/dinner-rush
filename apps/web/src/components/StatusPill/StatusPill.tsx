import { STATUS_META, type OrderStatus } from "../../design/tokens";
import styles from "./StatusPill.module.css";

export interface StatusPillProps {
  status: OrderStatus;
  late?: boolean;
}

/**
 * Renders exactly one glyph, colour and label per order state — see
 * DESIGN.md §3.3. `late` is a modifier, never a recolour of the underlying
 * state.
 */
export function StatusPill({ status, late = false }: StatusPillProps) {
  const meta = STATUS_META[status];
  return (
    <span data-status={status} className={`${styles.pill} ${late ? styles.late : ""}`}>
      <span className={styles.glyph} aria-hidden="true">
        {meta.glyph}
      </span>
      <span>{meta.label}</span>
      {late && <span className={styles["late-suffix"]}>· LATE</span>}
    </span>
  );
}
