import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Sparkline } from "./Sparkline";

describe("Sparkline", () => {
  it("renders 'no data' for an empty series", () => {
    render(<Sparkline data={[]} />);
    expect(screen.getByText("no data")).toBeInTheDocument();
  });

  it("renders a single point as a dot, not a line", () => {
    render(<Sparkline data={[7]} />);
    expect(screen.getByRole("img", { name: "Single data point" })).toBeInTheDocument();
  });

  it("labels a rising series", () => {
    render(<Sparkline data={[1, 2, 3]} />);
    expect(screen.getByRole("img", { name: "Rising trend" })).toBeInTheDocument();
  });

  it("labels a falling series", () => {
    render(<Sparkline data={[3, 2, 1]} />);
    expect(screen.getByRole("img", { name: "Falling trend" })).toBeInTheDocument();
  });
});
