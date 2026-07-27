import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { Toast } from "./Toast";

describe("Toast", () => {
  it("renders its message with a status role", () => {
    render(<Toast variant="info">Order accepted.</Toast>);
    expect(screen.getByRole("status")).toHaveTextContent("Order accepted.");
  });

  it("calls onDismiss when the dismiss button is clicked", async () => {
    const onDismiss = vi.fn();
    render(
      <Toast variant="info" onDismiss={onDismiss}>
        Order accepted.
      </Toast>,
    );
    await userEvent.click(screen.getByRole("button", { name: "Dismiss" }));
    expect(onDismiss).toHaveBeenCalledOnce();
  });

  it("has no dismiss button when onDismiss is not provided", () => {
    render(<Toast variant="info">Order accepted.</Toast>);
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });
});
