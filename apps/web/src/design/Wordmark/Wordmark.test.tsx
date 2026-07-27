import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Wordmark } from "./Wordmark";

describe("Wordmark", () => {
  it("renders DINNER RUSH as a single accessible name", () => {
    render(<Wordmark />);
    expect(screen.getByText(/DINNER/)).toBeInTheDocument();
    expect(screen.getByText("RUSH")).toBeInTheDocument();
  });
});
