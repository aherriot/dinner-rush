import type { Meta, StoryObj } from "@storybook/react-vite";
import { SystemMap } from "./SystemMap";
import type { NodeId, ServiceHealth } from "./systemMapState";

const meta = {
  title: "Components/SystemMap",
  component: SystemMap,
} satisfies Meta<typeof SystemMap>;

export default meta;
type Story = StoryObj<typeof meta>;

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

const SAMPLE_METRICS: Partial<Record<NodeId, string>> = {
  "front-of-house": "12 orders/min",
  kitchen: "7/12 slots busy",
  dispatch: "3 active trips",
  redis: "3 streams · 6 groups",
  simulator: "2 orders/15s",
  "front-of-house-db": "11 tables",
  "kitchen-db": "6 tables",
  "dispatch-db": "6 tables",
};

export const AllHealthy: Story = {
  args: { health: ALL_HEALTHY, metrics: SAMPLE_METRICS },
};

export const Degraded: Story = {
  name: "Degraded (oven_down + courier_offline scenarios)",
  args: {
    health: { ...ALL_HEALTHY, kitchen: "degraded", dispatch: "degraded" },
    metrics: {
      ...SAMPLE_METRICS,
      kitchen: "0/12 slots busy",
      dispatch: "0 active trips",
    },
  },
};

export const FrontOfHouseDown: Story = {
  name: "Front of house unreachable (cold start / outage)",
  args: {
    health: {
      ...ALL_HEALTHY,
      "front-of-house": "down",
      kitchen: "down",
      dispatch: "down",
      redis: "degraded",
      browser: "degraded",
      simulator: "unknown",
      "front-of-house-db": "down",
      "kitchen-db": "down",
      "dispatch-db": "down",
    },
  },
};

export const Loading: Story = {
  args: { health: ALL_HEALTHY, loading: true },
};

export const LiveActivity: Story = {
  name: "With an active event pulse",
  args: {
    health: ALL_HEALTHY,
    metrics: SAMPLE_METRICS,
    pulses: [{ id: "p1", edgeId: "kitchen-redis" }],
  },
};
