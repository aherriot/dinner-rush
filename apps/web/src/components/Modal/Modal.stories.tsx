import type { Meta, StoryObj } from "@storybook/react-vite";
import { useState } from "react";
import { Button } from "../Button/Button";
import { Modal } from "./Modal";

function Demo(props: { destructive?: boolean; title: string; description: string; confirmLabel: string }) {
  const [open, setOpen] = useState(true);
  return (
    <>
      <Button onClick={() => setOpen(true)}>Open modal</Button>
      <Modal open={open} onClose={() => setOpen(false)} onConfirm={() => setOpen(false)} {...props} />
    </>
  );
}

const meta = {
  title: "Components/Modal",
  component: Modal,
  args: {
    open: true,
    onClose: () => {},
    title: "Confirm",
  },
} satisfies Meta<typeof Modal>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Confirm: Story = {
  render: () => (
    <Demo title="Advance to baking?" description="This claims an oven slot immediately." confirmLabel="Advance" />
  ),
};

export const DestructiveConfirm: Story = {
  name: "Destructive confirm",
  render: () => (
    <Demo
      destructive
      title="Cancel this order?"
      description="The customer will be notified immediately. This cannot be undone."
      confirmLabel="Cancel order"
    />
  ),
};
