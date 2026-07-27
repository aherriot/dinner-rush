import styles from "./Wordmark.module.css";

/**
 * The Dinner Rush wordmark. DESIGN.md §8: defined once, imported, never
 * redrawn per surface.
 */
export function Wordmark() {
  return (
    <span className={styles.wordmark}>
      DINNER <span className={styles.second}>RUSH</span>
    </span>
  );
}
