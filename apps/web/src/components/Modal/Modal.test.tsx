import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { Modal } from "./Modal";

describe("Modal", () => {
  it("is absent from the DOM when closed", () => {
    render(<Modal open={false} onClose={vi.fn()} title="Confirm" />);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("renders title and description when open", () => {
    render(<Modal open onClose={vi.fn()} title="Cancel this order?" description="Are you sure?" />);
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(screen.getByText("Cancel this order?")).toBeInTheDocument();
    expect(screen.getByText("Are you sure?")).toBeInTheDocument();
  });

  it("calls onClose from the cancel button", async () => {
    const onClose = vi.fn();
    render(<Modal open onClose={onClose} title="Cancel this order?" />);
    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(onClose).toHaveBeenCalledOnce();
  });

  it("calls onConfirm from the confirm button, not onClose", async () => {
    const onClose = vi.fn();
    const onConfirm = vi.fn();
    render(<Modal open onClose={onClose} onConfirm={onConfirm} title="Cancel this order?" />);
    await userEvent.click(screen.getByRole("button", { name: "Confirm" }));
    expect(onConfirm).toHaveBeenCalledOnce();
    expect(onClose).not.toHaveBeenCalled();
  });

  it("omits the confirm/cancel row when hideActions is set", () => {
    render(<Modal open onClose={vi.fn()} title="Order #4471" hideActions />);
    expect(screen.queryByRole("button", { name: "Confirm" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Cancel" })).not.toBeInTheDocument();
  });
});
