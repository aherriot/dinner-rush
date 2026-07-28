import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { CourierQueue, type CourierRosterEntry } from "./CourierQueue";

const NOW = 1_700_000_000_000;

const couriers: CourierRosterEntry[] = [
  {
    id: "c1",
    name: "Ada",
    status: "active",
    trips: [
      { id: "t1", code: "4471", etaAtMs: NOW + 4 * 60_000 },
      { id: "t2", code: "4472", etaAtMs: NOW - 4 * 60_000 },
    ],
  },
  { id: "c2", name: "Grace", status: "idle", trips: [] },
];

describe("CourierQueue", () => {
  it("treats a trip exactly at its ETA (and before it) as on time", () => {
    const onTime: CourierRosterEntry[] = [
      { id: "c1", name: "Ada", status: "active", trips: [{ id: "t1", code: "1", etaAtMs: NOW }] },
    ];
    render(<CourierQueue couriers={onTime} now={NOW} />);
    expect(screen.getByText("on time")).toBeInTheDocument();
  });

  it("never reports 0m late — anything under a minute overdue reads as <1m late", () => {
    const barelyLate: CourierRosterEntry[] = [
      {
        id: "c1",
        name: "Ada",
        status: "active",
        trips: [{ id: "t1", code: "1", etaAtMs: NOW - 10_000 }],
      },
    ];
    render(<CourierQueue couriers={barelyLate} now={NOW} />);
    expect(screen.getByText("<1m late")).toBeInTheDocument();
  });

  it("renders every courier and their trips in order with an eta readout", () => {
    render(
      <CourierQueue
        couriers={couriers}
        backlog={{ readyCount: 0, oldestWaitingSeconds: null }}
        now={NOW}
      />,
    );
    expect(screen.getByText("Ada")).toBeInTheDocument();
    expect(screen.getByText("Grace")).toBeInTheDocument();
    expect(screen.getByText("4471")).toBeInTheDocument();
    expect(screen.getByText("on time")).toBeInTheDocument();
    expect(screen.getByText("4m late")).toBeInTheDocument();
    expect(screen.getByText("No active trips")).toBeInTheDocument();
  });

  it("renders the backlog callout with a count and oldest-waiting age", () => {
    render(
      <CourierQueue
        couriers={couriers}
        backlog={{ readyCount: 3, oldestWaitingSeconds: 912 }}
        now={NOW}
      />,
    );
    expect(screen.getByText("3 ready, oldest waiting 15m")).toBeInTheDocument();
  });

  it("renders a reassuring message when the backlog is confirmed empty", () => {
    render(
      <CourierQueue
        couriers={couriers}
        backlog={{ readyCount: 0, oldestWaitingSeconds: null }}
        now={NOW}
      />,
    );
    expect(screen.getByText("No backlog")).toBeInTheDocument();
  });

  it("distinguishes an unreachable backlog from a confirmed-empty one", () => {
    render(<CourierQueue couriers={couriers} backlog={null} now={NOW} />);
    expect(screen.getByText("Backlog unknown")).toBeInTheDocument();
  });

  it("renders the empty state when there are no couriers and no explicit state", () => {
    render(<CourierQueue couriers={[]} now={NOW} />);
    expect(screen.getByRole("status")).toHaveTextContent("No couriers online.");
  });

  it("renders a loading skeleton", () => {
    render(<CourierQueue state="loading" now={NOW} />);
    expect(screen.getByTestId("panel-skeleton")).toBeInTheDocument();
  });

  it("renders the error state", () => {
    render(<CourierQueue state="error" errorMessage="Couldn't reach dispatch." now={NOW} />);
    expect(screen.getByRole("alert")).toHaveTextContent("Couldn't reach dispatch.");
  });
});
