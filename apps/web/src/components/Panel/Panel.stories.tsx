import type { Meta, StoryObj } from "@storybook/react-vite";
import { Button } from "../Button/Button";
import { Panel } from "./Panel";

const meta = {
  title: "Components/Panel",
  component: Panel,
  args: {
    title: "Order feed",
    children: <p>42 orders in the last hour.</p>,
  },
} satisfies Meta<typeof Panel>;

export default meta;
type Story = StoryObj<typeof meta>;

export const WithTitle: Story = {};

export const WithoutTitle: Story = { args: { title: undefined } };

export const WithToolbar: Story = {
  args: { toolbar: <Button variant="ghost" size="small">Refresh</Button> },
};

export const Collapsible: Story = { args: { collapsible: true } };

export const CollapsibleClosed: Story = { args: { collapsible: true, defaultOpen: false } };

export const Loading: Story = { args: { state: "loading" } };

export const Empty: Story = { args: { state: "empty", emptyMessage: "No orders yet." } };

export const Error: Story = { args: { state: "error", errorMessage: "Couldn't reach the kitchen service." } };
