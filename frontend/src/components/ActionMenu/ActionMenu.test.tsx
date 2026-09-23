import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { ActionMenu } from "./ActionMenu";

const ITEMS = [
  { label: "Rename", value: "RENAME" },
  { label: "Delete", value: "DELETE" },
] as const;

describe("ActionMenu", () => {
  it("opens its items from a text trigger", async () => {
    const user = userEvent.setup();
    render(<ActionMenu items={ITEMS} label="Clean Up" onPick={vi.fn()} />);

    await user.click(screen.getByRole("button", { name: "Clean Up" }));

    expect(screen.getByRole("button", { name: "Rename" })).toBeInTheDocument();
  });

  it("names an icon trigger by its label", () => {
    render(<ActionMenu icon="more" items={ITEMS} label="List actions" onPick={vi.fn()} />);

    expect(screen.getByRole("button", { name: "List actions" })).toHaveAttribute(
      "aria-expanded",
      "false",
    );
  });

  it("reports the picked item and closes", async () => {
    const user = userEvent.setup();
    const onPick = vi.fn();
    render(<ActionMenu items={ITEMS} label="Clean Up" onPick={onPick} />);

    await user.click(screen.getByRole("button", { name: "Clean Up" }));
    await user.click(screen.getByRole("button", { name: "Delete" }));

    expect(onPick).toHaveBeenCalledWith("DELETE");
    expect(screen.queryByRole("button", { name: "Rename" })).not.toBeInTheDocument();
  });

  it("closes when the user clicks elsewhere", async () => {
    const user = userEvent.setup();
    render(
      <>
        <ActionMenu items={ITEMS} label="Clean Up" onPick={vi.fn()} />
        <p>Example List</p>
      </>,
    );

    await user.click(screen.getByRole("button", { name: "Clean Up" }));
    await user.click(screen.getByText("Example List"));

    expect(screen.queryByRole("button", { name: "Rename" })).not.toBeInTheDocument();
  });

  it("closes on Escape", async () => {
    const user = userEvent.setup();
    render(<ActionMenu items={ITEMS} label="Clean Up" onPick={vi.fn()} />);

    await user.click(screen.getByRole("button", { name: "Clean Up" }));
    await user.keyboard("{Escape}");

    expect(screen.queryByRole("button", { name: "Rename" })).not.toBeInTheDocument();
  });

  it("stays shut while disabled", () => {
    render(<ActionMenu disabled items={ITEMS} label="Template" onPick={vi.fn()} />);

    expect(screen.getByRole("button", { name: "Template" })).toBeDisabled();
  });
});
