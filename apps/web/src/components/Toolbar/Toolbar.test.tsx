import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ActionMenu, SegmentedControl, ToggleGroup } from "./Toolbar";

const SPEEDS = [
  { value: "1", label: "1×" },
  { value: "10", label: "10×" },
];

describe("SegmentedControl", () => {
  it("calls onChange with the selected value", async () => {
    const onChange = vi.fn();
    render(<SegmentedControl label="Speed" options={SPEEDS} value="1" onChange={onChange} />);
    await userEvent.click(screen.getByText("10×"));
    expect(onChange).toHaveBeenCalledWith("10");
  });
});

describe("ToggleGroup", () => {
  it("adds a value when toggled on", async () => {
    const onChange = vi.fn();
    render(<ToggleGroup options={SPEEDS} selected={["1"]} onChange={onChange} />);
    await userEvent.click(screen.getByText("10×"));
    expect(onChange).toHaveBeenCalledWith(["1", "10"]);
  });

  it("removes a value when toggled off", async () => {
    const onChange = vi.fn();
    render(<ToggleGroup options={SPEEDS} selected={["1", "10"]} onChange={onChange} />);
    await userEvent.click(screen.getByText("10×"));
    expect(onChange).toHaveBeenCalledWith(["1"]);
  });
});

describe("ActionMenu", () => {
  it("fires onSelect for the chosen item", async () => {
    const onSelect = vi.fn();
    render(<ActionMenu label="Chaos" items={[{ key: "a", label: "Friday rush", onSelect }]} />);
    await userEvent.click(screen.getByRole("button", { name: /chaos/i }));
    await userEvent.click(await screen.findByText("Friday rush"));
    expect(onSelect).toHaveBeenCalledOnce();
  });
});
