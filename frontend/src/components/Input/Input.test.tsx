import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { Input } from "./Input";

describe("Input", () => {
  it("is reachable by its label", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<Input id="first" label="First Name" onChange={onChange} value="" />);

    await user.type(screen.getByLabelText("First Name"), "A");

    expect(onChange).toHaveBeenCalledOnce();
  });

  it("describes itself with the helper text", () => {
    render(<Input helper="Use the international format." id="phone" label="Phone" />);

    expect(screen.getByLabelText("Phone")).toHaveAccessibleDescription(
      "Use the international format.",
    );
  });

  it("stays named by its label when the label is hidden", () => {
    render(<Input id="search" label="Search" labelHidden />);

    expect(screen.getByRole("textbox", { name: "Search" })).toBeInTheDocument();
  });
});
