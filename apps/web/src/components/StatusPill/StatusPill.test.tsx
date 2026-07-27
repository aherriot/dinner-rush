import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { STATUS_ORDER } from "../../design/tokens";
import { StatusPill } from "./StatusPill";

describe("StatusPill", () => {
  it.each(STATUS_ORDER)("renders a label for %s", (status) => {
    render(<StatusPill status={status} />);
    expect(screen.getByText(new RegExp(status === "picked_up" ? "Picked up" : status, "i"))).toBeInTheDocument();
  });

  it("never recolours the underlying state when late", () => {
    const { container: normal } = render(<StatusPill status="baking" />);
    const { container: late } = render(<StatusPill status="baking" late />);
    expect(normal.querySelector("[data-status]")?.getAttribute("data-status")).toBe("baking");
    expect(late.querySelector("[data-status]")?.getAttribute("data-status")).toBe("baking");
  });

  it("appends the LATE suffix only when late", () => {
    render(<StatusPill status="baking" late />);
    expect(screen.getByText("· LATE")).toBeInTheDocument();
  });
});
