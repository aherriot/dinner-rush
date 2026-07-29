import type { Meta, StoryObj } from "@storybook/react-vite";
import { CourierQueue, type CourierRosterEntry } from "./CourierQueue";

const meta = {
  title: "Components/CourierQueue",
  component: CourierQueue,
} satisfies Meta<typeof CourierQueue>;

export default meta;
type Story = StoryObj<typeof meta>;

const NOW = 1_700_000_000_000;

const couriers: CourierRosterEntry[] = [
  {
    id: "c1",
    name: "Ada",
    status: "active",
    trips: [
      { id: "t1", code: "4471", status: "delivering", etaAtMs: NOW + 4 * 60_000 },
      { id: "t2", code: "4472", status: "assigned", etaAtMs: NOW - 4 * 60_000 },
    ],
  },
  { id: "c2", name: "Grace", status: "idle", trips: [] },
  { id: "c3", name: "Alan", status: "idle", trips: [] },
  { id: "c4", name: "Sam", status: "offline", trips: [] },
];

export const Populated: Story = {
  args: {
    couriers,
    backlog: { readyCount: 3, oldestWaitingSeconds: 912 },
    now: NOW,
  },
};

export const NoBacklog: Story = {
  args: {
    couriers,
    backlog: { readyCount: 0, oldestWaitingSeconds: null },
    now: NOW,
  },
};

export const BacklogUnknown: Story = {
  name: "Backlog unknown (dispatch degraded)",
  args: {
    couriers,
    backlog: null,
    now: NOW,
  },
};

export const Loading: Story = {
  args: { state: "loading", now: NOW },
};

export const Empty: Story = {
  args: { couriers: [], backlog: { readyCount: 0, oldestWaitingSeconds: null }, now: NOW },
};

export const Error: Story = {
  args: { state: "error", errorMessage: "Couldn't reach dispatch.", now: NOW },
};
