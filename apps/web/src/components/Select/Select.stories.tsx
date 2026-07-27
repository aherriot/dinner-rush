import type { Meta, StoryObj } from "@storybook/react-vite";
import { useState } from "react";
import { userEvent, within } from "storybook/test";
import { Select, type SelectOption } from "./Select";

const OVEN_STATUS: SelectOption<"available" | "down">[] = [
  { value: "available", label: "Available" },
  { value: "down", label: "Down" },
];

function Controlled(props: { disabled?: boolean; error?: string }) {
  const [value, setValue] = useState<"available" | "down">("available");
  return <Select<"available" | "down"> label="Oven status" options={OVEN_STATUS} value={value} onChange={setValue} {...props} />;
}

const meta = {
  title: "Components/Select",
  component: Select,
  args: {
    options: OVEN_STATUS,
    value: "available",
    onChange: () => {},
  },
} satisfies Meta<typeof Select>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Default: Story = { render: () => <Controlled /> };
export const Disabled: Story = { render: () => <Controlled disabled /> };
export const WithError: Story = { render: () => <Controlled error="Choose a status" /> };

export const Open: Story = {
  render: () => <Controlled />,
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await userEvent.click(canvas.getByRole("button"));
  },
};
