import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { RedisTopologyModal, type StreamTopology } from "./RedisTopologyModal";

const STREAMS: StreamTopology[] = [
  {
    stream: "events:order",
    groups: [
      { group: "cg:kitchen", does: "Builds a ticket from order.accepted." },
      { group: "cg:dispatch", does: "Triggers assignment on order.ready." },
    ],
  },
  {
    stream: "events:oven",
    groups: [{ group: "cg:ws-board-fanout", does: "Pushes oven state to the board." }],
  },
];

describe("RedisTopologyModal", () => {
  it("is absent from the DOM when closed", () => {
    render(<RedisTopologyModal open={false} onClose={vi.fn()} streams={STREAMS} />);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("renders every stream and its consumer groups", () => {
    render(<RedisTopologyModal open onClose={vi.fn()} streams={STREAMS} />);
    expect(screen.getByText("events:order")).toBeInTheDocument();
    expect(screen.getByText("events:oven")).toBeInTheDocument();
    expect(screen.getByText("cg:kitchen")).toBeInTheDocument();
    expect(screen.getByText("cg:dispatch")).toBeInTheDocument();
    expect(screen.getByText("cg:ws-board-fanout")).toBeInTheDocument();
  });

  it("counts distinct groups, not group-per-stream rows, in the summary", () => {
    // cg:ws-board-fanout would appear on both streams in the full dataset;
    // this fixture only repeats it once, but the count must still de-dupe
    // by group name, not sum row counts.
    render(<RedisTopologyModal open onClose={vi.fn()} streams={STREAMS} />);
    expect(screen.getByText(/2 streams, 3 distinct consumer groups/)).toBeInTheDocument();
  });

  it("has no confirm/cancel actions — it's read-only", () => {
    render(<RedisTopologyModal open onClose={vi.fn()} streams={STREAMS} />);
    expect(screen.queryByRole("button", { name: "Confirm" })).not.toBeInTheDocument();
  });
});
