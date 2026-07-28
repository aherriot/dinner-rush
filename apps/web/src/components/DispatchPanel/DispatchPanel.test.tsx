import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { DispatchPanel, type CourierMapEntry } from "./DispatchPanel";

const couriers: CourierMapEntry[] = [
  { id: "c1", name: "Ada", status: "active", x: 50, y: 50 },
  { id: "c2", name: "Grace", status: "idle", x: 0, y: 0 },
];

describe("DispatchPanel", () => {
  it("renders the active trip count and every courier", () => {
    render(<DispatchPanel couriers={couriers} activeTripCount={6} />);
    expect(screen.getByText("6")).toBeInTheDocument();
    expect(screen.getByLabelText(/ada.*courier active/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/grace.*courier idle/i)).toBeInTheDocument();
  });

  it("positions a courier by percentage of the grid", () => {
    render(<DispatchPanel couriers={[{ id: "c1", status: "active", x: 25, y: 75 }]} gridSize={100} />);
    const dot = screen.getByRole("img", { name: /courier active/i });
    const pin = dot.parentElement;
    expect(pin).toHaveStyle({ left: "25%", top: "75%" });
  });

  it("renders the empty state when there are no couriers and no explicit state", () => {
    render(<DispatchPanel couriers={[]} />);
    expect(screen.getByRole("status")).toHaveTextContent("No couriers online.");
  });

  it("renders a loading skeleton", () => {
    render(<DispatchPanel state="loading" />);
    expect(screen.getByTestId("panel-skeleton")).toBeInTheDocument();
  });

  it("renders the error state", () => {
    render(<DispatchPanel state="error" errorMessage="Couldn't reach dispatch." />);
    expect(screen.getByRole("alert")).toHaveTextContent("Couldn't reach dispatch.");
  });
});
