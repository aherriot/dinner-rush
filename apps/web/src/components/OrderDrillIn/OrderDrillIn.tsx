import { Modal } from "../Modal/Modal";
import {
  OrderTimeline,
  type OrderTimelineState,
  type TimelineEvent,
} from "../OrderTimeline/OrderTimeline";
import styles from "./OrderDrillIn.module.css";

export interface OrderDrillInProps {
  /** `null` closes the modal — there's nothing else to gate on since this
   * is read-only and has no separate `open` concept from "which order". */
  code: string | null;
  events?: TimelineEvent[];
  state?: OrderTimelineState;
  errorMessage?: string;
  onClose: () => void;
}

/**
 * The board's per-order drill-in — a `Modal` wrapping the same
 * `OrderTimeline` the customer-facing tracker uses (`pages/OrderTracker`),
 * so an order's full status history reads identically in both places.
 * Purely props-driven like its siblings: the board page owns the initial
 * `/orders/{code}/timeline` fetch and appends live board-socket events for
 * whichever order is currently open.
 */
export function OrderDrillIn({
  code,
  events,
  state = "idle",
  errorMessage,
  onClose,
}: OrderDrillInProps) {
  return (
    <Modal open={code !== null} onClose={onClose} title={code ? `Order #${code}` : "Order"} hideActions>
      <div className={styles.body}>
        <OrderTimeline events={events} state={state} errorMessage={errorMessage} />
      </div>
    </Modal>
  );
}
