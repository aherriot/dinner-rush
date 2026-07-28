import type { Meta, StoryObj } from "@storybook/react-vite";
import type { TimelineEvent } from "../OrderTimeline/OrderTimeline";
import { OrderDrillIn } from "./OrderDrillIn";

const meta = {
  title: "Components/OrderDrillIn",
  component: OrderDrillIn,
  args: {
    code: "4471",
    onClose: () => {},
  },
} satisfies Meta<typeof OrderDrillIn>;

export default meta;
type Story = StoryObj<typeof meta>;

const EVENTS: TimelineEvent[] = [
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
];

export const Populated: Story = { args: { events: EVENTS } };
export const Loading: Story = { args: { state: "loading" } };
export const Empty: Story = { args: { state: "empty" } };
export const Error: Story = {
  args: { state: "error", errorMessage: "Couldn't load this order's timeline." },
};
