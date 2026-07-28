import type { Meta, StoryObj } from "@storybook/react-vite";
import { DispatchPanel, type CourierMapEntry } from "./DispatchPanel";

const meta = {
  title: "Components/DispatchPanel",
  component: DispatchPanel,
} satisfies Meta<typeof DispatchPanel>;

export default meta;
type Story = StoryObj<typeof meta>;

const couriers: CourierMapEntry[] = [
  { id: "c1", name: "Ada", status: "active", x: 62, y: 40 },
  { id: "c2", name: "Grace", status: "idle", x: 20, y: 70 },
  { id: "c3", name: "Alan", status: "active", x: 55, y: 55, selected: true },
  { id: "c4", name: "Katherine", status: "offline", x: 80, y: 15 },
];

export const Populated: Story = {
  args: { couriers, activeTripCount: 6 },
};

export const Loading: Story = {
  args: { state: "loading" },
};

export const Empty: Story = {
  args: { couriers: [], activeTripCount: 0 },
};

export const Error: Story = {
  args: { state: "error", errorMessage: "Couldn't reach dispatch." },
};
