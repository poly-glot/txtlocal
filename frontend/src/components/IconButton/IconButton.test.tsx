import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { IconButton } from "./IconButton";

describe("IconButton", () => {
  it("is named by its label", () => {
    render(<IconButton icon="plus" label="Add contact" />);

    expect(screen.getByRole("button", { name: "Add contact" })).toBeInTheDocument();
  });

  it("reports a click", async () => {
    const user = userEvent.setup();
    const onClick = vi.fn();
    render(<IconButton icon="plus" label="Add contact" onClick={onClick} />);

    await user.click(screen.getByRole("button", { name: "Add contact" }));

    expect(onClick).toHaveBeenCalledOnce();
  });
});
