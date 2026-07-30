import type { Meta, StoryObj } from "@storybook/react-vite";
import type { StreamTopology } from "./RedisTopologyModal";
import { RedisTopologyModal } from "./RedisTopologyModal";

const meta = {
  title: "Components/RedisTopologyModal",
  component: RedisTopologyModal,
  args: {
    open: true,
    onClose: () => {},
  },
} satisfies Meta<typeof RedisTopologyModal>;

export default meta;
type Story = StoryObj<typeof meta>;

const STREAMS: StreamTopology[] = [
  {
    stream: "events:order",
    groups: [
      { group: "cg:kitchen", does: "Builds a ticket from order.accepted." },
      { group: "cg:dispatch", does: "Caches the dropoff, triggers assignment on order.ready." },
      { group: "cg:analytics", does: "Increments an EventTypeCounter row per event type." },
      { group: "cg:order-sync", does: "Mirrors transitions back onto front-of-house's Order.status." },
      { group: "cg:ws-fanout", does: "Pushes to the per-order channel OrderTracker uses." },
      { group: "cg:ws-board-fanout", does: "Pushes to the board's own socket." },
    ],
  },
  {
    stream: "events:oven",
    groups: [{ group: "cg:ws-board-fanout", does: "Pushes oven state changes to the board." }],
  },
  {
    stream: "events:courier",
    groups: [
      { group: "cg:order-sync", does: "Mirrors courier/trip transitions onto Order.status." },
      { group: "cg:ws-board-fanout", does: "Pushes courier events to the board." },
    ],
  },
];

export const Populated: Story = {
  args: { streams: STREAMS },
};
