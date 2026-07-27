import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { KitchenPanel, type OvenViewModel } from "./KitchenPanel";

const ovens: OvenViewModel[] = [
  {
    id: "oven-1",
    name: "Oven 1",
    slots: [{ status: "occupied", progress: 40, label: "4400" }, { status: "free" }],
  },
];

describe("KitchenPanel", () => {
  it("renders queue depth and every oven's slots", () => {
    render(<KitchenPanel ovens={ovens} queueDepth={5} />);
    expect(screen.getByText("5")).toBeInTheDocument();
    expect(screen.getByText("Oven 1")).toBeInTheDocument();
    expect(screen.getByLabelText(/oven slot: occupied/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/oven slot: free/i)).toBeInTheDocument();
  });

  it("renders the empty state when there are no ovens and no explicit state", () => {
    render(<KitchenPanel ovens={[]} />);
    expect(screen.getByRole("status")).toHaveTextContent("No ovens configured.");
  });

  it("renders a loading skeleton", () => {
    render(<KitchenPanel state="loading" />);
    expect(screen.getByTestId("panel-skeleton")).toBeInTheDocument();
  });

  it("renders the error state", () => {
    render(<KitchenPanel state="error" errorMessage="Couldn't reach kitchen." />);
    expect(screen.getByRole("alert")).toHaveTextContent("Couldn't reach kitchen.");
  });
});
