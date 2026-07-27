import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { Panel } from "./Panel";

describe("Panel", () => {
  it("renders children in the idle state", () => {
    render(<Panel title="Kitchen">Content</Panel>);
    expect(screen.getByText("Content")).toBeInTheDocument();
  });

  it("renders a loading skeleton instead of children", () => {
    render(
      <Panel title="Kitchen" state="loading">
        Content
      </Panel>,
    );
    expect(screen.queryByText("Content")).not.toBeInTheDocument();
    expect(screen.getByTestId("panel-skeleton")).toBeInTheDocument();
  });

  it("renders the empty message", () => {
    render(
      <Panel title="Kitchen" state="empty" emptyMessage="No tickets">
        Content
      </Panel>,
    );
    expect(screen.getByRole("status")).toHaveTextContent("No tickets");
  });

  it("renders the error message with an alert role", () => {
    render(
      <Panel title="Kitchen" state="error" errorMessage="Kitchen unreachable">
        Content
      </Panel>,
    );
    expect(screen.getByRole("alert")).toHaveTextContent("Kitchen unreachable");
  });

  it("toggles a collapsible panel closed and open", async () => {
    render(
      <Panel title="Kitchen" collapsible>
        Content
      </Panel>,
    );
    expect(screen.getByText("Content")).toBeVisible();
    await userEvent.click(screen.getByRole("button", { name: "Kitchen" }));
    expect(screen.queryByText("Content")).not.toBeInTheDocument();
  });
});
