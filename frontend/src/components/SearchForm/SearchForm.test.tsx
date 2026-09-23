import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { SearchForm } from "./SearchForm";

describe("SearchForm", () => {
  it("searches for the draft when the user presses Enter", async () => {
    const user = userEvent.setup();
    const onSearch = vi.fn();
    render(<SearchForm id="search" label="Search lists" onSearch={onSearch} />);

    await user.type(screen.getByRole("searchbox", { name: "Search lists" }), "gold{Enter}");

    expect(onSearch).toHaveBeenCalledWith("gold");
  });

  it("keeps the default placeholder unless given one", () => {
    render(<SearchForm id="search" label="Search" onSearch={vi.fn()} />);

    expect(screen.getByPlaceholderText("Search...")).toBeInTheDocument();
  });
});
