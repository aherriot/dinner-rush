import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { DataTable, type DataTableColumn } from "./DataTable";

interface Row {
  id: string;
  name: string;
}

const COLUMNS: DataTableColumn<Row>[] = [
  { key: "name", header: "Name", sortable: true, render: (row) => row.name },
];

const ROWS: Row[] = [
  { id: "1", name: "Alice" },
  { id: "2", name: "Bob" },
];

describe("DataTable", () => {
  it("renders a row per item", () => {
    render(<DataTable columns={COLUMNS} rows={ROWS} rowKey={(row) => row.id} />);
    expect(screen.getByText("Alice")).toBeInTheDocument();
    expect(screen.getByText("Bob")).toBeInTheDocument();
  });

  it("renders the empty message when there are no rows", () => {
    render(<DataTable columns={COLUMNS} rows={[]} rowKey={(row) => row.id} emptyMessage="No rows" />);
    expect(screen.getByRole("status")).toHaveTextContent("No rows");
  });

  it("renders skeleton rows while loading, not the data", () => {
    render(<DataTable columns={COLUMNS} rows={ROWS} rowKey={(row) => row.id} state="loading" />);
    expect(screen.queryByText("Alice")).not.toBeInTheDocument();
  });

  it("calls onSort with the column key", async () => {
    const onSort = vi.fn();
    render(<DataTable columns={COLUMNS} rows={ROWS} rowKey={(row) => row.id} onSort={onSort} />);
    await userEvent.click(screen.getByRole("button", { name: "Name" }));
    expect(onSort).toHaveBeenCalledWith("name");
  });

  it("only renders a windowed subset when virtualised", () => {
    const manyRows: Row[] = Array.from({ length: 500 }, (_, i) => ({ id: String(i), name: `Row ${i}` }));
    render(<DataTable columns={COLUMNS} rows={manyRows} rowKey={(row) => row.id} virtualize viewportHeightPx={200} rowHeightPx={28} />);
    const renderedRows = screen.getAllByText(/^Row \d+$/);
    expect(renderedRows.length).toBeLessThan(manyRows.length);
  });

  it("calls onRowClick with the clicked row", async () => {
    const onRowClick = vi.fn();
    render(<DataTable columns={COLUMNS} rows={ROWS} rowKey={(row) => row.id} onRowClick={onRowClick} />);
    await userEvent.click(screen.getByText("Alice"));
    expect(onRowClick).toHaveBeenCalledWith(ROWS[0]);
  });

  it("calls onRowClick on Enter for keyboard users", async () => {
    const onRowClick = vi.fn();
    render(<DataTable columns={COLUMNS} rows={ROWS} rowKey={(row) => row.id} onRowClick={onRowClick} />);
    screen.getByText("Alice").closest("tr")?.focus();
    await userEvent.keyboard("{Enter}");
    expect(onRowClick).toHaveBeenCalledWith(ROWS[0]);
  });

  it("rows aren't focusable when onRowClick is omitted", () => {
    render(<DataTable columns={COLUMNS} rows={ROWS} rowKey={(row) => row.id} />);
    expect(screen.getByText("Alice").closest("tr")).not.toHaveAttribute("tabIndex");
  });
});
