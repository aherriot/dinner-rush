import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { SystemMap } from "./SystemMap";
import type { NodeId, ServiceHealth } from "./systemMapState";

const ALL_HEALTHY: Record<NodeId, ServiceHealth> = {
  simulator: "healthy",
  browser: "healthy",
  "front-of-house": "healthy",
  kitchen: "healthy",
  dispatch: "healthy",
  redis: "healthy",
  "front-of-house-db": "healthy",
  "kitchen-db": "healthy",
  "dispatch-db": "healthy",
};

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("SystemMap", () => {
  it("renders every service node's name", () => {
    render(<SystemMap health={ALL_HEALTHY} />);
    expect(screen.getByText("Simulator")).toBeInTheDocument();
    expect(screen.getByText("Front of House")).toBeInTheDocument();
    expect(screen.getByText("Kitchen")).toBeInTheDocument();
    expect(screen.getByText("Dispatch")).toBeInTheDocument();
    expect(screen.getByText("Redis")).toBeInTheDocument();
    expect(screen.getByText("Board (you)")).toBeInTheDocument();
  });

  it("renders each service's own database as its own node", () => {
    render(<SystemMap health={ALL_HEALTHY} />);
    // Node labels are the real Postgres DB names (compose.yaml POSTGRES_DB) —
    // "front_of_house"/"kitchen"/"dispatch" — distinct from the service box labels
    // ("Front of House"/"Kitchen"/"Dispatch") right next to them.
    expect(screen.getByText("front_of_house")).toBeInTheDocument();
    expect(screen.getByText("kitchen")).toBeInTheDocument();
    expect(screen.getByText("dispatch")).toBeInTheDocument();
    expect(screen.getAllByText("Postgres 16")).toHaveLength(3);
  });

  it("lists every one of a database's real tables directly on the node", () => {
    render(<SystemMap health={ALL_HEALTHY} />);
    // kitchen's real tables (schemaData.ts) — not a count, the actual names.
    expect(screen.getByText("oven")).toBeInTheDocument();
    expect(screen.getByText("oven_slot")).toBeInTheDocument();
    expect(screen.getByText("station")).toBeInTheDocument();
    expect(screen.getByText("ticket")).toBeInTheDocument();
    // front-of-house's own outbox/processed_event appear once each, not merged
    // with kitchen's or dispatch's same-named tables.
    expect(screen.getAllByText("outbox")).toHaveLength(3);
  });

  it("lists Redis's real streams and consumer groups directly on the node", () => {
    render(<SystemMap health={ALL_HEALTHY} />);
    // events:order/events:oven also appear as edge labels elsewhere on the
    // diagram, so this asserts presence via getAllByText rather than
    // uniqueness — Redis's own copy is one of those matches.
    expect(screen.getAllByText("events:order").length).toBeGreaterThan(0);
    expect(screen.getAllByText("events:oven").length).toBeGreaterThan(0);
    expect(screen.getByText("events:courier")).toBeInTheDocument();
    expect(screen.getByText("cg:kitchen")).toBeInTheDocument();
    expect(screen.getByText("cg:ws-board-fanout")).toBeInTheDocument();
    expect(screen.getByText(/Streams \(3\)/)).toBeInTheDocument();
    expect(screen.getByText(/Groups \(6\)/)).toBeInTheDocument();
  });

  it("opens the database schema modal when a database node is clicked", async () => {
    render(<SystemMap health={ALL_HEALTHY} />);
    await userEvent.click(screen.getByRole("button", { name: /kitchen database/i }));
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(screen.getByText(/kitchen — entity relationships/i)).toBeInTheDocument();
    // The schema modal's own column list, not just the on-canvas table name.
    expect(screen.getByText("oven_slot_id")).toBeInTheDocument();
  });

  it("opens the database schema modal on Enter/Space, not just click", async () => {
    render(<SystemMap health={ALL_HEALTHY} />);
    const dispatchDbNode = screen.getByRole("button", { name: /dispatch database/i });
    dispatchDbNode.focus();
    await userEvent.keyboard("{Enter}");
    expect(screen.getByText(/dispatch — entity relationships/i)).toBeInTheDocument();
  });

  it("opens the Redis topology modal when the Redis node is clicked", async () => {
    render(<SystemMap health={ALL_HEALTHY} />);
    await userEvent.click(screen.getByRole("button", { name: /redis — 3 streams/i }));
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(screen.getByText(/streams and consumer groups/i)).toBeInTheDocument();
  });

  it("closes the open modal without leaving another one behind", async () => {
    render(<SystemMap health={ALL_HEALTHY} />);
    await userEvent.click(screen.getByRole("button", { name: /front_of_house database/i }));
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    await userEvent.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("summarises full health in the diagram's accessible name", () => {
    render(<SystemMap health={ALL_HEALTHY} />);
    expect(screen.getByRole("group", { name: /all 9 services healthy/i })).toBeInTheDocument();
  });

  it("disambiguates a database node from its same-named service in the accessible name", () => {
    render(<SystemMap health={{ ...ALL_HEALTHY, kitchen: "down", "kitchen-db": "down" }} />);
    const diagram = screen.getByRole("group", { name: /kitchen down/i });
    expect(diagram).toHaveAccessibleName(/kitchen DB down/i);
  });

  it("shows a metric line only for a node the caller supplied one for", () => {
    render(
      <SystemMap
        health={ALL_HEALTHY}
        metrics={{ "front-of-house": "12 orders/min", kitchen: "4/12 slots busy" }}
      />,
    );
    expect(screen.getByText("12 orders/min")).toBeInTheDocument();
    expect(screen.getByText("4/12 slots busy")).toBeInTheDocument();
    expect(screen.queryByText(/active trip/)).not.toBeInTheDocument();
  });

  it("names each unhealthy service in the accessible summary", () => {
    render(<SystemMap health={{ ...ALL_HEALTHY, kitchen: "down", dispatch: "degraded" }} />);
    const diagram = screen.getByRole("group", { name: /kitchen down/i });
    expect(diagram).toHaveAccessibleName(/dispatch degraded/i);
  });

  it("uses honest, non-alarming copy for an idle simulator rather than 'unknown'", () => {
    render(<SystemMap health={{ ...ALL_HEALTHY, simulator: "unknown" }} />);
    expect(screen.getByText("Idle")).toBeInTheDocument();
  });

  it("uses honest, non-alarming copy for a websocket-down front-of-house rather than a bare 'Degraded'", () => {
    render(<SystemMap health={{ ...ALL_HEALTHY, "front-of-house": "degraded" }} />);
    expect(screen.getByText("Polling REST")).toBeInTheDocument();
  });

  it("shows the loading skeleton when the initial snapshot hasn't arrived", () => {
    render(<SystemMap health={ALL_HEALTHY} loading />);
    expect(screen.getByTestId("panel-skeleton")).toBeInTheDocument();
  });

  it("renders a travelling pulse dot for an active edge when motion is allowed", () => {
    const { container } = render(
      <SystemMap health={ALL_HEALTHY} pulses={[{ id: "p1", edgeId: "kitchen-redis" }]} />,
    );
    expect(container.querySelectorAll("circle[r]").length).toBeGreaterThan(0);
  });

  it("flashes the edge instead of animating a dot when reduced motion is preferred", () => {
    vi.stubGlobal(
      "matchMedia",
      (query: string) =>
        ({
          matches: true,
          media: query,
          onchange: null,
          addListener: () => {},
          removeListener: () => {},
          addEventListener: () => {},
          removeEventListener: () => {},
          dispatchEvent: () => false,
        }) as MediaQueryList,
    );

    const { container } = render(
      <SystemMap health={ALL_HEALTHY} pulses={[{ id: "p1", edgeId: "kitchen-redis" }]} />,
    );
    expect(container.querySelectorAll("circle[r]").length).toBe(0);
    expect(container.querySelector("line[data-flash]")).not.toBeNull();
  });

  it("renders exactly the three database nodes front-of-house/kitchen/dispatch own", () => {
    const { container } = render(<SystemMap health={ALL_HEALTHY} />);
    expect(container.querySelectorAll('rect[class*="db-node"]')).toHaveLength(3);
  });

  it("never draws a travelling pulse on a database-ownership edge", () => {
    // "db" edges are structural (an ER-diagram-style foreign-key line), not
    // traffic — pulses target real edge ids, so this just confirms nothing
    // downstream tries to animate one even if asked to.
    const { container } = render(
      <SystemMap health={ALL_HEALTHY} pulses={[{ id: "p1", edgeId: "front-of-house-front-of-house-db" }]} />,
    );
    expect(container.querySelectorAll("circle[r]").length).toBe(0);
  });
});
