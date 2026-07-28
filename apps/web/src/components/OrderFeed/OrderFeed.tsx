import { DataTable, type DataTableColumn } from "../DataTable/DataTable";
import { Panel, type PanelState } from "../Panel/Panel";
import { StatusPill } from "../StatusPill/StatusPill";
import type { OrderStatus } from "../../design/tokens";
import styles from "./OrderFeed.module.css";

export interface OrderFeedRow {
  code: string;
  status: OrderStatus;
  late?: boolean;
}

export interface OrderFeedProps {
  orders?: OrderFeedRow[];
  state?: PanelState;
  errorMessage?: string;
}

const columns: DataTableColumn<OrderFeedRow>[] = [
  {
    key: "code",
    header: "Order",
    render: (row) => <span className={styles.code}>#{row.code}</span>,
  },
  {
    key: "status",
    header: "Status",
    render: (row) => <StatusPill status={row.status} late={row.late} />,
  },
];

/**
 * The board's ORDER FEED panel (PIZZA.md's demo mockup, DESIGN.md §10 —
 * 280px column) — most-recent-first, built from `DataTable` + `StatusPill`
 * so status rendering reads DESIGN.md §3.3 and nothing else. Live rows are
 * pushed in by the board page from `/ws/board`; this component is purely
 * props-driven.
 */
export function OrderFeed({ orders = [], state = "idle", errorMessage }: OrderFeedProps) {
  return (
    <Panel
      title="Order feed"
      state={orders.length === 0 && state === "idle" ? "empty" : state}
      errorMessage={errorMessage}
      emptyMessage="No orders yet."
    >
      <DataTable
        columns={columns}
        rows={orders}
        rowKey={(row) => row.code}
        density="dense"
        virtualize
        rowHeightPx={28}
        viewportHeightPx={640}
      />
    </Panel>
  );
}
