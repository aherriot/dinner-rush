import type { Meta, StoryObj } from "@storybook/react-vite";
import { OrderTimeline, type TimelineEvent } from "./OrderTimeline";

const meta = {
  title: "Components/OrderTimeline",
  component: OrderTimeline,
} satisfies Meta<typeof OrderTimeline>;

export default meta;
type Story = StoryObj<typeof meta>;

const IN_FLIGHT: TimelineEvent[] = [
  { event: "place", from_status: null, to_status: "placed", occurred_at: "2026-01-01T12:00:00Z" },
  {
    event: "accept",
    from_status: "placed",
    to_status: "accepted",
    occurred_at: "2026-01-01T12:00:02Z",
  },
  {
    event: "enqueue",
    from_status: "accepted",
    to_status: "queued",
    occurred_at: "2026-01-01T12:00:04Z",
  },
  {
    event: "start_bake",
    from_status: "prepping",
    to_status: "baking",
    occurred_at: "2026-01-01T12:00:12Z",
  },
];

const DELIVERED: TimelineEvent[] = [
  ...IN_FLIGHT,
  {
    event: "finish_bake",
    from_status: "baking",
    to_status: "boxed",
    occurred_at: "2026-01-01T12:00:20Z",
  },
  {
    event: "mark_ready",
    from_status: "boxed",
    to_status: "ready",
    occurred_at: "2026-01-01T12:00:22Z",
  },
  {
    event: "assign",
    from_status: "ready",
    to_status: "assigned",
    occurred_at: "2026-01-01T12:00:24Z",
  },
  {
    event: "deliver",
    from_status: "delivering",
    to_status: "delivered",
    occurred_at: "2026-01-01T12:00:40Z",
  },
];

const REJECTED: TimelineEvent[] = [
  { event: "place", from_status: null, to_status: "placed", occurred_at: "2026-01-01T12:00:00Z" },
  {
    event: "reject",
    from_status: "placed",
    to_status: "rejected",
    occurred_at: "2026-01-01T12:00:01Z",
  },
];

export const InFlight: Story = { args: { events: IN_FLIGHT } };
export const Delivered: Story = { args: { events: DELIVERED } };
export const Rejected: Story = { args: { events: REJECTED } };
export const Loading: Story = { args: { state: "loading" } };
export const Empty: Story = { args: { state: "empty" } };
export const Error: Story = {
  args: { state: "error", errorMessage: "Couldn't reach the gateway." },
};
