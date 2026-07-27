import type { Meta, StoryObj } from "@storybook/react-vite";
import { Sparkline } from "./Sparkline";

const meta = {
  title: "Components/Sparkline",
  component: Sparkline,
} satisfies Meta<typeof Sparkline>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Flat: Story = { args: { data: [5, 5, 5, 5, 5, 5] } };
export const Rising: Story = { args: { data: [2, 3, 4, 6, 8, 12, 18] } };
export const Falling: Story = { args: { data: [18, 12, 8, 6, 4, 3, 2] } };
export const SinglePoint: Story = { args: { data: [7] } };
export const NoData: Story = { args: { data: [] } };
