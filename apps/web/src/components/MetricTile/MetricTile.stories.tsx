import type { Meta, StoryObj } from "@storybook/react-vite";
import { MetricTile } from "./MetricTile";

const meta = {
  title: "Components/MetricTile",
  component: MetricTile,
  args: { label: "Orders / min" },
} satisfies Meta<typeof MetricTile>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Value: Story = { args: { value: 42 } };
export const ValueWithDelta: Story = {
  name: "Value + delta",
  args: { value: 42, delta: { value: "6", direction: "up" } },
};
export const ValueWithNegativeDelta: Story = {
  args: { value: 42, delta: { value: "3", direction: "down" } },
};
export const NoData: Story = { args: {} };
export const Stale: Story = { args: { value: 42, stale: true } };
