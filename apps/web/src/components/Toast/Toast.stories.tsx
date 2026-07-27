import type { Meta, StoryObj } from "@storybook/react-vite";
import { Toast, ToastStack } from "./Toast";

const meta = {
  title: "Components/Toast",
  component: Toast,
  args: {
    children: "Order DR-1042 accepted.",
  },
} satisfies Meta<typeof Toast>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Info: Story = { args: { variant: "info" } };
export const Success: Story = { args: { variant: "success", children: "Order DR-1042 delivered." } };
export const Warning: Story = { args: { variant: "warning", children: "Oven 3 approaching capacity." } };
export const Error: Story = { args: { variant: "error", children: "Kitchen service unreachable." } };

export const StackedThree: Story = {
  name: "Stacked ×3",
  args: { variant: "info" },
  render: () => (
    <ToastStack>
      <Toast variant="info">Order DR-1042 accepted.</Toast>
      <Toast variant="success">Order DR-1039 delivered.</Toast>
      <Toast variant="warning">Oven 3 approaching capacity.</Toast>
    </ToastStack>
  ),
};
