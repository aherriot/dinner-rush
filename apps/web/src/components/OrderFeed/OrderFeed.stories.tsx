import type { Meta, StoryObj } from "@storybook/react-vite";
import { OrderFeed, type OrderFeedRow } from "./OrderFeed";

const meta = {
  title: "Components/OrderFeed",
  component: OrderFeed,
} satisfies Meta<typeof OrderFeed>;

export default meta;
type Story = StoryObj<typeof meta>;

const orders: OrderFeedRow[] = [
  { code: "4471", status: "placed" },
  { code: "4470", status: "baking" },
  { code: "4469", status: "ready" },
  { code: "4468", status: "rejected" },
  { code: "4467", status: "delivering", late: true },
  { code: "4466", status: "delivered" },
];

export const Populated: Story = {
  args: { orders },
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
