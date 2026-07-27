import type { Meta, StoryObj } from "@storybook/react-vite";
import { OvenSlot } from "./OvenSlot";

const meta = {
  title: "Components/OvenSlot",
  component: OvenSlot,
} satisfies Meta<typeof OvenSlot>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Free: Story = { args: { status: "free" } };
export const Reserved: Story = { args: { status: "reserved" } };
export const Occupied0: Story = { args: { status: "occupied", progress: 0 } };
export const Occupied50: Story = { args: { status: "occupied", progress: 50 } };
export const Occupied100: Story = { args: { status: "occupied", progress: 100 } };
export const Down: Story = { args: { status: "down" } };

export const AllStates: Story = {
  args: { status: "free" },
  render: () => (
    <div style={{ display: "flex", gap: 8 }}>
      <OvenSlot status="free" />
      <OvenSlot status="reserved" />
      <OvenSlot status="occupied" progress={30} />
      <OvenSlot status="occupied" progress={100} />
      <OvenSlot status="down" />
    </div>
  ),
};
