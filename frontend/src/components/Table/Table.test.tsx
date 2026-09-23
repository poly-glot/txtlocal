import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { Table } from "./Table";
import { toggleSort } from "./sort";

interface Row {
  id: string;
  name: string;
}

const COLUMNS = [{ header: "NAME", key: "name", render: (row: Row) => row.name }];
const ROWS: Row[] = [{ id: "1", name: "Ada" }];

describe("Table", () => {
  it("shows the empty sentence when there are no rows", () => {
    render(<Table columns={COLUMNS} emptyText="No results" keyOf={(row) => row.id} rows={[]} />);

    expect(screen.getByText("No results")).toBeInTheDocument();
  });

  it("asks to sort by the clicked header", async () => {
    const user = userEvent.setup();
    const onSort = vi.fn();
    render(
      <Table
        columns={COLUMNS}
        emptyText="No results"
        keyOf={(row) => row.id}
        onSort={onSort}
        rows={ROWS}
        sort={{ direction: "asc", key: "name" }}
      />,
    );

    await user.click(screen.getByRole("button", { name: "NAME" }));

    expect(onSort).toHaveBeenCalledWith("name");
    expect(screen.getByRole("columnheader", { name: "NAME" })).toHaveAttribute(
      "aria-sort",
      "ascending",
    );
  });

  it("keeps a column that opts out of sorting as plain text", () => {
    render(
      <Table
        columns={[{ header: "NAME", key: "name", render: (row) => row.name, sortable: false }]}
        emptyText="No results"
        keyOf={(row) => row.id}
        onSort={vi.fn()}
        rows={ROWS}
      />,
    );

    expect(screen.queryByRole("button", { name: "NAME" })).not.toBeInTheDocument();
  });
});

describe("toggleSort", () => {
  it.each([
    {
      key: "notes",
      label: "a new column sorts ascending",
      next: { direction: "asc", key: "notes" },
      sort: { direction: "desc", key: "username" },
    },
    {
      key: "username",
      label: "the same column flips to descending",
      next: { direction: "desc", key: "username" },
      sort: { direction: "asc", key: "username" },
    },
    {
      key: "username",
      label: "the same column flips back to ascending",
      next: { direction: "asc", key: "username" },
      sort: { direction: "desc", key: "username" },
    },
  ] as const)("$label", ({ key, next, sort }) => {
    expect(toggleSort(sort, key)).toEqual(next);
  });
});
