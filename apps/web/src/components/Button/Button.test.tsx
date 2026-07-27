import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import userEvent from "@testing-library/user-event";
import { Button } from "./Button";

describe("Button", () => {
  it("fires onClick when enabled", async () => {
    const onClick = vi.fn();
    render(<Button onClick={onClick}>Confirm</Button>);
    await userEvent.click(screen.getByRole("button", { name: "Confirm" }));
    expect(onClick).toHaveBeenCalledOnce();
  });

  it("does not fire onClick while loading", async () => {
    const onClick = vi.fn();
    render(
      <Button onClick={onClick} loading>
        Confirm
      </Button>,
    );
    const button = screen.getByRole("button", { name: "Confirm" });
    expect(button).toBeDisabled();
    expect(button).toHaveAttribute("aria-busy", "true");
  });

  it("does not fire onClick while disabled", async () => {
    const onClick = vi.fn();
    render(
      <Button onClick={onClick} disabled>
        Confirm
      </Button>,
    );
    await userEvent.click(screen.getByRole("button", { name: "Confirm" }));
    expect(onClick).not.toHaveBeenCalled();
  });
});
