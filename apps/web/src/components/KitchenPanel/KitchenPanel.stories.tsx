import type { Meta, StoryObj } from "@storybook/react-vite";
import { KitchenPanel, type OvenViewModel } from "./KitchenPanel";

const meta = {
  title: "Components/KitchenPanel",
  component: KitchenPanel,
} satisfies Meta<typeof KitchenPanel>;

export default meta;
type Story = StoryObj<typeof meta>;

const ovens: OvenViewModel[] = [
  {
    id: "oven-1",
    name: "Oven 1",
    slots: [
      { status: "occupied", progress: 80, label: "4402" },
      { status: "occupied", progress: 20, label: "4407" },
      { status: "free" },
      { status: "free" },
      { status: "reserved" },
      { status: "free" },
    ],
  },
  {
    id: "oven-2",
    name: "Oven 2",
    slots: [
      { status: "occupied", progress: 55, label: "4401" },
      { status: "free" },
      { status: "free" },
      { status: "free" },
      { status: "free" },
      { status: "free" },
    ],
  },
  {
    id: "oven-3",
    name: "Oven 3",
    slots: [
      { status: "down" },
      { status: "down" },
      { status: "down" },
      { status: "down" },
    ],
  },
];

export const Populated: Story = {
  args: { ovens, queueDepth: 7 },
};

export const Loading: Story = {
  args: { state: "loading" },
};

export const Empty: Story = {
  args: { ovens: [], queueDepth: 0 },
};

export const Error: Story = {
  args: { state: "error", errorMessage: "Couldn't reach kitchen." },
};
