import type { Meta, StoryObj } from "@storybook/react-vite";
import { STATUS_ORDER } from "../../design/tokens";
import { StatusPill } from "./StatusPill";

const meta = {
  title: "Components/StatusPill",
  component: StatusPill,
} satisfies Meta<typeof StatusPill>;

export default meta;
type Story = StoryObj<typeof meta>;

export const AllStates: Story = {
  args: { status: "placed" },
  render: () => (
    <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
      {STATUS_ORDER.map((status) => (
        <StatusPill key={status} status={status} />
      ))}
    </div>
  ),
};

export const AllStatesLate: Story = {
  name: "All states — late modifier",
  args: { status: "placed", late: true },
  render: () => (
    <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
      {STATUS_ORDER.map((status) => (
        <StatusPill key={status} status={status} late />
      ))}
    </div>
  ),
};

export const Rejected: Story = { args: { status: "rejected" } };
export const Failed: Story = { args: { status: "failed" } };
export const Baking: Story = { args: { status: "baking" } };
export const BakingLate: Story = { args: { status: "baking", late: true } };
export const Ready: Story = { args: { status: "ready" } };
