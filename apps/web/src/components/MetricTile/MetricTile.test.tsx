import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { MetricTile } from "./MetricTile";

describe("MetricTile", () => {
  it("renders the value", () => {
    render(<MetricTile label="Orders / min" value={42} />);
    expect(screen.getByText("42")).toBeInTheDocument();
  });

  it("renders an em dash when there is no data", () => {
    render(<MetricTile label="Orders / min" />);
    expect(screen.getByText("—")).toBeInTheDocument();
  });

  it("renders the delta direction", () => {
    render(<MetricTile label="Orders / min" value={42} delta={{ value: "6", direction: "up" }} />);
    expect(screen.getByText(/6/)).toBeInTheDocument();
  });
});
