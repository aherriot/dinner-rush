import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { OrderFeed, type OrderFeedRow } from "./OrderFeed";

const orders: OrderFeedRow[] = [
  { code: "4471", status: "placed", placedAgo: "12s ago" },
  { code: "4468", status: "rejected", placedAgo: "5m ago" },
];

describe("OrderFeed", () => {
  it("renders every order's code, status and placed-ago time", () => {
    render(<OrderFeed orders={orders} />);
    expect(screen.getByText("#4471")).toBeInTheDocument();
    expect(screen.getByText("#4468")).toBeInTheDocument();
    // "Placed" is ambiguous at the document level — it's both the "Placed"
    // column header and the first row's status pill label — so these are
    // scoped to their own row rather than a bare `getByText`.
    const firstRow = screen.getByText("#4471").closest("tr")!;
    const secondRow = screen.getByText("#4468").closest("tr")!;
    expect(within(firstRow).getByText("Placed")).toBeInTheDocument();
    expect(within(secondRow).getByText("Rejected")).toBeInTheDocument();
    expect(within(firstRow).getByText("12s ago")).toBeInTheDocument();
    expect(within(secondRow).getByText("5m ago")).toBeInTheDocument();
  });

  it("calls onSelect with the order code when a row is clicked", async () => {
    const onSelect = vi.fn();
    render(<OrderFeed orders={orders} onSelect={onSelect} />);
    await userEvent.click(screen.getByText("#4471"));
    expect(onSelect).toHaveBeenCalledWith("4471");
  });

  it("isn't clickable when onSelect is omitted", () => {
    render(<OrderFeed orders={orders} />);
    expect(screen.getByText("#4471").closest("tr")).not.toHaveAttribute("tabIndex");
  });

  it("renders the late modifier without recolouring the status", () => {
    render(<OrderFeed orders={[{ code: "1", status: "baking", late: true }]} />);
    expect(screen.getByText("· LATE")).toBeInTheDocument();
  });

  it("renders the empty state when there are no orders and no explicit state", () => {
    render(<OrderFeed orders={[]} />);
    expect(screen.getByRole("status")).toHaveTextContent("No orders yet.");
  });

  it("renders a loading skeleton", () => {
    render(<OrderFeed state="loading" />);
    expect(screen.getByTestId("panel-skeleton")).toBeInTheDocument();
  });

  it("renders the error state", () => {
    render(<OrderFeed state="error" errorMessage="Couldn't reach the order feed." />);
    expect(screen.getByRole("alert")).toHaveTextContent("Couldn't reach the order feed.");
  });
});
