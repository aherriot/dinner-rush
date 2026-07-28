import { rejectionReasonLabel } from "../../design/rejectionReasons";
import type { OrderStatus } from "../../design/tokens";
import { StatusPill } from "../StatusPill/StatusPill";
import styles from "./OrderTimeline.module.css";

export interface TimelineEvent {
  event: string;
  from_status: OrderStatus | null;
  to_status: OrderStatus;
  occurred_at: string;
  /** Only set on the `reject` event — why this order never got cooked. */
  reason?: string | null;
  /** Kitchen queue depth at the moment of the quote — only meaningful
   * alongside `reason: "at_capacity"`; other reasons never call kitchen. */
  queue_depth?: number | null;
}

export type OrderTimelineState = "idle" | "loading" | "empty" | "error";

export interface OrderTimelineProps {
  events?: TimelineEvent[];
  state?: OrderTimelineState;
  errorMessage?: string;
}

function formatTime(iso: string): string {
  return new Date(iso).toLocaleTimeString(undefined, {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

/**
 * A vertical read-out of an order's status history — domain visualisation,
 * no Headless UI equivalent (same bucket as StatusPill/OvenSlot per
 * DESIGN.md §7). Renders `GET /orders/{code}/timeline` directly.
 */
export function OrderTimeline({ events = [], state = "idle", errorMessage }: OrderTimelineProps) {
  if (state === "loading") {
    return (
      <div className={styles.list} aria-busy="true">
        <div className={styles.skeleton} data-testid="timeline-skeleton">
          <div className={styles["skeleton-row"]} />
          <div className={styles["skeleton-row"]} />
          <div className={styles["skeleton-row"]} />
        </div>
      </div>
    );
  }

  if (state === "error") {
    return (
      <div className={styles.state} role="alert">
        {errorMessage ?? "Couldn't load the order timeline."}
      </div>
    );
  }

  if (state === "empty" || events.length === 0) {
    return (
      <div className={styles.state} role="status">
        No status updates yet.
      </div>
    );
  }

  return (
    <ol className={styles.list}>
      {events.map((item) => (
        <li key={`${item.event}-${item.occurred_at}`} className={styles.row}>
          <span className={styles.time}>{formatTime(item.occurred_at)}</span>
          <div className={styles.detail}>
            <StatusPill status={item.to_status} />
            {item.to_status === "rejected" && item.reason && (
              <p className={styles.reason}>
                {rejectionReasonLabel(item.reason)}
                {item.reason === "at_capacity" && item.queue_depth != null && (
                  <> — queue depth {item.queue_depth}</>
                )}
              </p>
            )}
          </div>
        </li>
      ))}
    </ol>
  );
}
