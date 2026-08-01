import type { Meta, StoryObj } from "@storybook/react-vite";
import { useState } from "react";
import { StatusBar, type ChaosScenarioOption, type SpeedValue } from "./StatusBar";

const meta = {
  title: "Components/StatusBar",
  component: StatusBar,
} satisfies Meta<typeof StatusBar>;

export default meta;
type Story = StoryObj<typeof meta>;

const scenarios: ChaosScenarioOption[] = [
  { name: "friday_rush", label: "Friday rush" },
  { name: "oven_down", label: "Oven down" },
  { name: "courier_offline", label: "Courier offline" },
  { name: "ingredient_shortage", label: "Ingredient shortage" },
];

function Interactive(args: Parameters<typeof StatusBar>[0]) {
  const [speed, setSpeed] = useState<SpeedValue>(args.speed);
  const [active, setActive] = useState<string[]>(args.activeScenarios ?? []);
  return (
    <StatusBar
      {...args}
      speed={speed}
      onSpeedChange={setSpeed}
      activeScenarios={active}
      onStartScenario={(name) => setActive((current) => [...new Set([...current, name])])}
      onStopScenario={(name) => setActive((current) => current.filter((n) => n !== name))}
    />
  );
}

export const Calm: Story = {
  render: Interactive,
  args: {
    speed: 1,
    onSpeedChange: () => {},
    ordersPerMinute: 6,
    p95LatePercent: 2,
    streamPending: 0,
    promiseErrorP95Seconds: -8,
    scenarios,
    activeScenarios: [],
    onStartScenario: () => {},
    onStopScenario: () => {},
    connected: true,
  },
};

export const RushActive: Story = {
  render: Interactive,
  args: {
    ...Calm.args,
    speed: 10,
    ordersPerMinute: 38,
    p95LatePercent: 22,
    streamPending: 14,
    promiseErrorP95Seconds: 47,
    activeScenarios: ["friday_rush", "oven_down"],
  },
};

export const NoData: Story = {
  args: {
    speed: 1,
    onSpeedChange: () => {},
    scenarios,
    onStartScenario: () => {},
    onStopScenario: () => {},
  },
};

export const Reconnecting: Story = {
  args: {
    ...NoData.args,
    connected: false,
  },
};
