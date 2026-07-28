import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import type { TimelineEvent } from "../OrderTimeline/OrderTimeline";
import { OrderDrillIn } from "./OrderDrillIn";

const EVENTS: TimelineEvent[] = [
  { event: "place", from_status: null, to_status: "placed", occurred_at: "2026-01-01T12:00:00Z" },
];

describe("OrderDrillIn", () => {
  it("is absent from the DOM when there's no order to show", () => {
    render(<OrderDrillIn code={null} onClose={vi.fn()} />);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("titles the dialog with the order code and renders its timeline", () => {
    render(<OrderDrillIn code="4471" events={EVENTS} onClose={vi.fn()} />);
    expect(screen.getByRole("dialog")).toHaveTextContent("Order #4471");
    expect(screen.getByText("Placed")).toBeInTheDocument();
  });

  it("has no confirm/cancel row — it's read-only", () => {
    render(<OrderDrillIn code="4471" events={EVENTS} onClose={vi.fn()} />);
    expect(screen.queryByRole("button", { name: "Confirm" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Cancel" })).not.toBeInTheDocument();
  });

  it("closes on Escape, via Headless UI's own Dialog behaviour", async () => {
    const onClose = vi.fn();
    render(<OrderDrillIn code="4471" events={EVENTS} onClose={onClose} />);
    await userEvent.keyboard("{Escape}");
    expect(onClose).toHaveBeenCalledOnce();
  });
});
