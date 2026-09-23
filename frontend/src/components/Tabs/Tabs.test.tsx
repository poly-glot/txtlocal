import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { Tabs } from "./Tabs";

const TABS = ["Subaccounts", "General"] as const;

describe("Tabs", () => {
  it("marks the selected tab", () => {
    render(<Tabs onSelect={vi.fn()} selected="General" tabs={TABS} />);

    expect(screen.getByRole("tab", { name: "General" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("tab", { name: "Subaccounts" })).toHaveAttribute(
      "aria-selected",
      "false",
    );
  });

  it("reports the tab that was clicked", async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();
    render(<Tabs onSelect={onSelect} selected="Subaccounts" tabs={TABS} />);

    await user.click(screen.getByRole("tab", { name: "General" }));

    expect(onSelect).toHaveBeenCalledWith("General");
  });
});
