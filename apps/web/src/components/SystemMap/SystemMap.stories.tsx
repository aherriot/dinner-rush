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
  gateway: "healthy",
  kitchen: "healthy",
  dispatch: "healthy",
  redis: "healthy",
  "gateway-db": "healthy",
  "kitchen-db": "healthy",
  "dispatch-db": "healthy",
};

const SAMPLE_METRICS: Partial<Record<NodeId, string>> = {
  gateway: "12 orders/min",
  kitchen: "7/12 slots busy",
  dispatch: "3 active trips",
  redis: "3 streams · 6 groups",
  simulator: "2 orders/15s",
  "gateway-db": "11 tables",
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

export const GatewayDown: Story = {
  name: "Gateway unreachable (cold start / outage)",
  args: {
    health: {
      ...ALL_HEALTHY,
      gateway: "down",
      kitchen: "down",
      dispatch: "down",
      redis: "degraded",
      browser: "degraded",
      simulator: "unknown",
      "gateway-db": "down",
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
