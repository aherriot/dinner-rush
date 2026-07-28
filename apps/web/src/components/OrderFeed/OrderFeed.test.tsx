import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { OrderFeed, type OrderFeedRow } from "./OrderFeed";

const orders: OrderFeedRow[] = [
  { code: "4471", status: "placed" },
  { code: "4468", status: "rejected" },
];

describe("OrderFeed", () => {
  it("renders every order's code and status", () => {
    render(<OrderFeed orders={orders} />);
    expect(screen.getByText("#4471")).toBeInTheDocument();
    expect(screen.getByText("#4468")).toBeInTheDocument();
    expect(screen.getByText("Placed")).toBeInTheDocument();
    expect(screen.getByText("Rejected")).toBeInTheDocument();
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
