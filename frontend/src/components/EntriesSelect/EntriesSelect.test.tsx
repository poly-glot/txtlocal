import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { EntriesSelect } from "./EntriesSelect";

describe("EntriesSelect", () => {
  it("offers twenty, fifty and a hundred entries", () => {
    render(<EntriesSelect id="entries" onChange={vi.fn()} value={20} />);

    expect(screen.getAllByRole("option").map((option) => option.textContent)).toEqual([
      "20",
      "50",
      "100",
    ]);
  });

  it("reports the size the user picks as a number", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<EntriesSelect id="entries" onChange={onChange} value={20} />);

    await user.selectOptions(screen.getByRole("combobox", { name: "Show Entries" }), "50");

    expect(onChange).toHaveBeenCalledWith(50);
  });
});
