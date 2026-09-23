import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { RowAction } from "./RowAction";

describe("RowAction", () => {
  it("reports a click", async () => {
    const user = userEvent.setup();
    const onClick = vi.fn();
    render(
      <RowAction onClick={onClick} tone="danger">
        Remove
      </RowAction>,
    );

    await user.click(screen.getByRole("button", { name: "Remove" }));

    expect(onClick).toHaveBeenCalledOnce();
  });
});
