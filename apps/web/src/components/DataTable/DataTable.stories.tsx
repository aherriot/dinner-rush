import type { Meta, StoryObj } from "@storybook/react-vite";
import { useState } from "react";
import { DataTable, type DataTableColumn } from "./DataTable";

interface OrderRow {
  code: string;
  customer: string;
  total: string;
  status: string;
}

const COLUMNS: DataTableColumn<OrderRow>[] = [
  { key: "code", header: "Order", sortable: true, render: (row) => row.code },
  { key: "customer", header: "Customer", render: (row) => row.customer },
  { key: "total", header: "Total", sortable: true, render: (row) => row.total },
  { key: "status", header: "Status", render: (row) => row.status },
];

function makeRows(count: number): OrderRow[] {
  return Array.from({ length: count }, (_, index) => ({
    code: `DR-${1000 + index}`,
    customer: `Customer ${index + 1}`,
    total: `$${(12 + (index % 20)).toFixed(2)}`,
    status: ["placed", "baking", "ready", "delivered"][index % 4] ?? "placed",
  }));
}

const ROWS = makeRows(8);

const meta = {
  title: "Components/DataTable",
  component: DataTable<OrderRow>,
  args: {
    columns: COLUMNS,
    rows: ROWS,
    rowKey: (row: OrderRow) => row.code,
  },
} satisfies Meta<typeof DataTable<OrderRow>>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Dense: Story = { args: { density: "dense" } };
export const Default: Story = { args: { density: "default" } };

export const Sorted: Story = {
  render: () => {
    function Demo() {
      const [sortKey, setSortKey] = useState("total");
      const [sortDirection, setSortDirection] = useState<"asc" | "desc">("desc");
      return (
        <DataTable
          columns={COLUMNS}
          rows={ROWS}
          rowKey={(row) => row.code}
          sortKey={sortKey}
          sortDirection={sortDirection}
          onSort={(key) => {
            if (key === sortKey) setSortDirection((d) => (d === "asc" ? "desc" : "asc"));
            else setSortKey(key);
          }}
        />
      );
    }
    return <Demo />;
  },
};

export const Empty: Story = { args: { rows: [], state: "empty", emptyMessage: "No orders in the queue." } };

export const Loading: Story = { args: { state: "loading" } };

export const Virtualised500Rows: Story = {
  name: "500-row virtualised",
  args: { rows: makeRows(500), virtualize: true, viewportHeightPx: 320 },
};

export const Clickable: Story = { args: { onRowClick: () => {} } };
