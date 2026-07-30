import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { DatabaseSchemaModal, type SchemaTable } from "./DatabaseSchemaModal";

const TABLES: SchemaTable[] = [
  {
    name: "courier",
    columns: [
      { name: "id", type: "uuid", primaryKey: true },
      { name: "status", type: "varchar" },
    ],
  },
  {
    name: "trip",
    columns: [
      { name: "id", type: "uuid", primaryKey: true },
      { name: "courier_id", type: "uuid", references: "courier.id" },
    ],
  },
];

describe("DatabaseSchemaModal", () => {
  it("is absent from the DOM when closed", () => {
    render(
      <DatabaseSchemaModal open={false} onClose={vi.fn()} databaseName="dispatch" tables={TABLES} />,
    );
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("renders every table name and column", () => {
    render(
      <DatabaseSchemaModal open onClose={vi.fn()} databaseName="dispatch" tables={TABLES} />,
    );
    expect(screen.getByText("courier")).toBeInTheDocument();
    expect(screen.getByText("trip")).toBeInTheDocument();
    expect(screen.getByText("courier_id")).toBeInTheDocument();
  });

  it("marks primary key columns and annotates foreign keys with their target", () => {
    render(
      <DatabaseSchemaModal open onClose={vi.fn()} databaseName="dispatch" tables={TABLES} />,
    );
    expect(screen.getAllByText("PK")).toHaveLength(2);
    expect(screen.getByText("→ courier.id")).toBeInTheDocument();
  });

  it("highlights the referenced table while its foreign-key reference is hovered, and clears on unhover", () => {
    render(
      <DatabaseSchemaModal open onClose={vi.fn()} databaseName="dispatch" tables={TABLES} />,
    );
    const courierTable = screen.getByText("courier").closest("table")!;
    const reference = screen.getByRole("button", { name: "→ courier.id" });

    expect(courierTable).not.toHaveAttribute("data-highlighted");

    fireEvent.mouseEnter(reference);
    expect(courierTable).toHaveAttribute("data-highlighted", "true");

    fireEvent.mouseLeave(reference);
    expect(courierTable).not.toHaveAttribute("data-highlighted");
  });

  it("highlights the referenced table on keyboard focus, and clears on blur", () => {
    render(
      <DatabaseSchemaModal open onClose={vi.fn()} databaseName="dispatch" tables={TABLES} />,
    );
    const courierTable = screen.getByText("courier").closest("table")!;
    const reference = screen.getByRole("button", { name: "→ courier.id" });

    fireEvent.focus(reference);
    expect(courierTable).toHaveAttribute("data-highlighted", "true");

    fireEvent.blur(reference);
    expect(courierTable).not.toHaveAttribute("data-highlighted");
  });

  it("has no confirm/cancel actions — it's read-only", () => {
    render(
      <DatabaseSchemaModal open onClose={vi.fn()} databaseName="dispatch" tables={TABLES} />,
    );
    expect(screen.queryByRole("button", { name: "Confirm" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Cancel" })).not.toBeInTheDocument();
  });
});
