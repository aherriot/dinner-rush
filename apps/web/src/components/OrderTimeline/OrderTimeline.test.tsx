import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { OrderTimeline, type TimelineEvent } from "./OrderTimeline";

const EVENTS: TimelineEvent[] = [
  { event: "place", from_status: null, to_status: "placed", occurred_at: "2026-01-01T12:00:00Z" },
  {
    event: "accept",
    from_status: "placed",
    to_status: "accepted",
    occurred_at: "2026-01-01T12:00:02Z",
  },
];

describe("OrderTimeline", () => {
  it("renders one status pill per event, in order", () => {
    render(<OrderTimeline events={EVENTS} />);
    const rows = screen.getAllByRole("listitem");
    expect(rows).toHaveLength(2);
    expect(rows[0]).toHaveTextContent("Placed");
    expect(rows[1]).toHaveTextContent("Accepted");
  });

  it("shows an empty message when there are no events", () => {
    render(<OrderTimeline events={[]} />);
    expect(screen.getByRole("status")).toHaveTextContent(/no status updates/i);
  });

  it("shows a loading skeleton", () => {
    render(<OrderTimeline state="loading" />);
    expect(screen.getByTestId("timeline-skeleton")).toBeInTheDocument();
  });

  it("shows an error message", () => {
    render(<OrderTimeline state="error" errorMessage="network down" />);
    expect(screen.getByRole("alert")).toHaveTextContent("network down");
  });

  it("shows the human-readable rejection reason on a rejected event", () => {
    const events: TimelineEvent[] = [
      {
        event: "reject",
        from_status: "placed",
        to_status: "rejected",
        occurred_at: "2026-01-01T12:00:01Z",
        reason: "outside_range",
      },
    ];
    render(<OrderTimeline events={events} />);
    expect(screen.getByText("Outside delivery range")).toBeInTheDocument();
  });

  it("includes queue depth alongside an at-capacity rejection", () => {
    const events: TimelineEvent[] = [
      {
        event: "reject",
        from_status: "placed",
        to_status: "rejected",
        occurred_at: "2026-01-01T12:00:01Z",
        reason: "at_capacity",
        queue_depth: 42,
      },
    ];
    render(<OrderTimeline events={events} />);
    expect(screen.getByText(/Kitchen at capacity.*queue depth 42/)).toBeInTheDocument();
  });
});
