/** Human-readable copy for `Order.rejection_reason` / `OrderStatusEvent.reason`
 * (services/front_of_house/src/front_of_house/orders/rejection.py). Not a design token —
 * plain copy, shared so the board drill-in and the customer tracker read
 * identically. */
export const REJECTION_REASON_LABELS: Record<string, string> = {
  at_capacity: "Kitchen at capacity",
  item_unavailable: "Item unavailable",
  outside_range: "Outside delivery range",
};

export function rejectionReasonLabel(reason: string): string {
  return REJECTION_REASON_LABELS[reason] ?? reason;
}
