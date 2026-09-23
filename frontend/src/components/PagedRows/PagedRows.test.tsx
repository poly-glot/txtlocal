import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { PagedRows } from "./PagedRows";

interface ListProps {
  rows: readonly string[];
}

const rowsOf = (count: number) =>
  Array.from({ length: count }, (_, index) => `Row ${String(index + 1)}`);

function List({ rows }: ListProps) {
  return (
    <PagedRows rows={rows}>
      {(page) => (
        <ul>
          {page.map((row) => (
            <li key={row}>{row}</li>
          ))}
        </ul>
      )}
    </PagedRows>
  );
}

describe("PagedRows", () => {
  it("returns to the first page when the only row on the last page goes", async () => {
    const user = userEvent.setup();
    const view = render(<List rows={rowsOf(21)} />);
    await user.click(screen.getByRole("button", { name: "Next" }));

    view.rerender(<List rows={rowsOf(20)} />);

    expect(screen.getByText("Row 1")).toBeInTheDocument();
  });

  it("offers no previous page once it is back on the first", async () => {
    const user = userEvent.setup();
    const view = render(<List rows={rowsOf(21)} />);
    await user.click(screen.getByRole("button", { name: "Next" }));

    view.rerender(<List rows={rowsOf(20)} />);

    expect(screen.getByRole("button", { name: "Previous" })).toBeDisabled();
  });
});
