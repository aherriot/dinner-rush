import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { OvenSlot } from "./OvenSlot";

describe("OvenSlot", () => {
  it("describes its status accessibly", () => {
    render(<OvenSlot status="free" />);
    expect(screen.getByRole("img", { name: "Oven slot: free" })).toBeInTheDocument();
  });

  it("includes bake progress in the accessible name when occupied", () => {
    render(<OvenSlot status="occupied" progress={65} />);
    expect(screen.getByRole("img", { name: "Oven slot: occupied, 65% baked" })).toBeInTheDocument();
  });
});
