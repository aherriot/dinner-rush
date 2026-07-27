import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Meter } from "./Meter";

describe("Meter", () => {
  it("exposes the value as an accessible meter", () => {
    render(<Meter label="Kitchen capacity" value={42} />);
    const meter = screen.getByRole("meter", { name: "Kitchen capacity" });
    expect(meter).toHaveAttribute("aria-valuenow", "42");
  });

  it("renders 'down' instead of a percentage when out of service", () => {
    render(<Meter label="Kitchen capacity" value={0} status="down" />);
    expect(screen.getByText("down")).toBeInTheDocument();
  });
});
