import type { Meta, StoryObj } from "@storybook/react-vite";
import { Button, type ButtonVariant } from "./Button";

const VARIANTS: ButtonVariant[] = ["primary", "secondary", "ghost", "danger"];

const meta = {
  title: "Components/Button",
  component: Button,
  args: {
    children: "Confirm",
  },
} satisfies Meta<typeof Button>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Primary: Story = { args: { variant: "primary" } };
export const Secondary: Story = { args: { variant: "secondary" } };
export const Ghost: Story = { args: { variant: "ghost" } };
export const Danger: Story = { args: { variant: "danger", children: "Delete order" } };

export const Disabled: Story = {
  render: () => (
    <div style={{ display: "flex", gap: 8 }}>
      {VARIANTS.map((variant) => (
        <Button key={variant} variant={variant} disabled>
          Confirm
        </Button>
      ))}
    </div>
  ),
};

export const Loading: Story = {
  render: () => (
    <div style={{ display: "flex", gap: 8 }}>
      {VARIANTS.map((variant) => (
        <Button key={variant} variant={variant} loading>
          Confirm
        </Button>
      ))}
    </div>
  ),
};

export const Small: Story = {
  render: () => (
    <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
      {VARIANTS.map((variant) => (
        <Button key={variant} variant={variant} size="small">
          Confirm
        </Button>
      ))}
    </div>
  ),
};

export const AllVariants: Story = {
  name: "Default / Hover / Active / Focus (interact to see states)",
  render: () => (
    <div style={{ display: "flex", gap: 8 }}>
      {VARIANTS.map((variant) => (
        <Button key={variant} variant={variant}>
          Confirm
        </Button>
      ))}
    </div>
  ),
};
