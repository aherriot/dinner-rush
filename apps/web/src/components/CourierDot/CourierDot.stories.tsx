import type { Meta, StoryObj } from "@storybook/react-vite";
import { CourierDot } from "./CourierDot";

const meta = {
  title: "Components/CourierDot",
  component: CourierDot,
} satisfies Meta<typeof CourierDot>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Idle: Story = { args: { status: "idle" } };
export const Active: Story = { args: { status: "active" } };
export const Offline: Story = { args: { status: "offline" } };
export const Selected: Story = { args: { status: "active", selected: true } };

export const AllStates: Story = {
  args: { status: "idle" },
  render: () => (
    <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
      <CourierDot status="idle" />
      <CourierDot status="active" />
      <CourierDot status="offline" />
      <CourierDot status="active" selected />
    </div>
  ),
};
