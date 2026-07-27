import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { Select, type SelectOption } from "./Select";

const OPTIONS: SelectOption<"available" | "down">[] = [
  { value: "available", label: "Available" },
  { value: "down", label: "Down" },
];

describe("Select", () => {
  it("calls onChange with the selected option's value", async () => {
    const onChange = vi.fn();
    render(<Select label="Oven status" options={OPTIONS} value="available" onChange={onChange} />);
    await userEvent.click(screen.getByRole("button"));
    await userEvent.click(await screen.findByRole("option", { name: "Down" }));
    expect(onChange).toHaveBeenCalledWith("down");
  });

  it("renders the error message when provided", () => {
    render(<Select options={OPTIONS} value="available" onChange={vi.fn()} error="Required" />);
    expect(screen.getByText("Required")).toBeInTheDocument();
  });

  it("disables the trigger when disabled", () => {
    render(<Select options={OPTIONS} value="available" onChange={vi.fn()} disabled />);
    expect(screen.getByRole("button")).toBeDisabled();
  });
});
