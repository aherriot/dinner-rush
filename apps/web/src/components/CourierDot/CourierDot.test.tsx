import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { CourierDot } from "./CourierDot";

describe("CourierDot", () => {
  it("describes idle status accessibly", () => {
    render(<CourierDot status="idle" name="Sam" />);
    expect(screen.getByRole("img", { name: "Sam — courier idle" })).toBeInTheDocument();
  });

  it("mentions selection in the accessible name", () => {
    render(<CourierDot status="active" selected />);
    expect(screen.getByRole("img", { name: "courier active, selected" })).toBeInTheDocument();
  });
});
