import type { Meta, StoryObj } from "@storybook/react-vite";
import { OrderFeed, type OrderFeedRow } from "./OrderFeed";

const meta = {
  title: "Components/OrderFeed",
  component: OrderFeed,
} satisfies Meta<typeof OrderFeed>;

export default meta;
type Story = StoryObj<typeof meta>;

const orders: OrderFeedRow[] = [
  { code: "4471", status: "placed", placedAgo: "12s ago" },
  { code: "4470", status: "baking", placedAgo: "1m ago" },
  { code: "4469", status: "ready", placedAgo: "4m ago" },
  { code: "4468", status: "rejected", placedAgo: "5m ago" },
  { code: "4467", status: "delivering", late: true, placedAgo: "18m ago" },
  { code: "4466", status: "delivered", placedAgo: "26m ago" },
];

export const Populated: Story = {
  args: { orders },
};

export const Selectable: Story = {
  args: { orders, onSelect: () => {} },
};

export const Loading: Story = {
  args: { state: "loading" },
};

export const Empty: Story = {
  args: { orders: [] },
};

export const Error: Story = {
  args: { state: "error", errorMessage: "Couldn't reach the order feed." },
};
