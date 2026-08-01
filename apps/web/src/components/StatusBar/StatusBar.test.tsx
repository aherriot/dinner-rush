import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { StatusBar, type ChaosScenarioOption } from "./StatusBar";

const scenarios: ChaosScenarioOption[] = [
  { name: "friday_rush", label: "Friday rush" },
  { name: "oven_down", label: "Oven down" },
];

describe("StatusBar", () => {
  it("renders the clock, rate and p95 metrics", () => {
    render(
      <StatusBar
        speed={1}
        onSpeedChange={() => {}}
        ordersPerMinute={38}
        p95LatePercent={8}
        scenarios={scenarios}
        onStartScenario={() => {}}
        onStopScenario={() => {}}
      />,
    );
    expect(screen.getByTestId("board-clock")).toBeInTheDocument();
    expect(screen.getByText("38/min")).toBeInTheDocument();
    expect(screen.getByText("8%")).toBeInTheDocument();
  });

  it("renders the Prometheus-backed backlog and promise-accuracy metrics", () => {
    render(
      <StatusBar
        speed={1}
        onSpeedChange={() => {}}
        streamPending={14}
        promiseErrorP95Seconds={47}
        scenarios={scenarios}
        onStartScenario={() => {}}
        onStopScenario={() => {}}
      />,
    );
    expect(screen.getByText("14")).toBeInTheDocument();
    expect(screen.getByText("+47s")).toBeInTheDocument();
  });

  it("signs a negative promise error without a leading plus", () => {
    render(
      <StatusBar
        speed={1}
        onSpeedChange={() => {}}
        promiseErrorP95Seconds={-8}
        scenarios={scenarios}
        onStartScenario={() => {}}
        onStopScenario={() => {}}
      />,
    );
    expect(screen.getByText("-8s")).toBeInTheDocument();
  });

  it("calls onSpeedChange with a number when a speed segment is picked", () => {
    const onSpeedChange = vi.fn();
    render(
      <StatusBar
        speed={1}
        onSpeedChange={onSpeedChange}
        scenarios={scenarios}
        onStartScenario={() => {}}
        onStopScenario={() => {}}
      />,
    );
    fireEvent.click(screen.getByText("10x"));
    expect(onSpeedChange).toHaveBeenCalledWith(10);
  });

  it("starts a scenario from the chaos menu", async () => {
    const onStartScenario = vi.fn();
    render(
      <StatusBar
        speed={1}
        onSpeedChange={() => {}}
        scenarios={scenarios}
        onStartScenario={onStartScenario}
        onStopScenario={() => {}}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /chaos/i }));
    fireEvent.click(await screen.findByText("Friday rush"));
    expect(onStartScenario).toHaveBeenCalledWith("friday_rush");
  });

  it("renders active scenarios as stoppable chips", () => {
    const onStopScenario = vi.fn();
    render(
      <StatusBar
        speed={1}
        onSpeedChange={() => {}}
        scenarios={scenarios}
        activeScenarios={["oven_down"]}
        onStartScenario={() => {}}
        onStopScenario={onStopScenario}
      />,
    );
    fireEvent.click(screen.getByText("Oven down"));
    expect(onStopScenario).toHaveBeenCalledWith("oven_down");
  });

  it("shows a reconnecting indicator when not connected", () => {
    render(
      <StatusBar
        speed={1}
        onSpeedChange={() => {}}
        scenarios={scenarios}
        onStartScenario={() => {}}
        onStopScenario={() => {}}
        connected={false}
      />,
    );
    expect(screen.getByLabelText("Reconnecting")).toBeInTheDocument();
  });
});
