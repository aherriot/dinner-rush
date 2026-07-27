import type { Meta, StoryObj } from "@storybook/react-vite";
import { Meter } from "./Meter";

const meta = {
  title: "Components/Meter",
  component: Meter,
  args: { label: "Kitchen capacity" },
} satisfies Meta<typeof Meter>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Zero: Story = { args: { value: 0 } };
export const TwentyFive: Story = { args: { value: 25 } };
export const Fifty: Story = { args: { value: 50 } };
export const OneHundred: Story = { args: { value: 100 } };
export const AtCapacity: Story = { args: { value: 92, status: "at-capacity" } };
export const OverCapacity: Story = { args: { value: 100, status: "over-capacity" } };
export const Down: Story = { args: { value: 0, status: "down" } };
