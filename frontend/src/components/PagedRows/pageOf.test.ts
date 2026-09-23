import { describe, expect, it } from "vitest";

import { pageOf } from "./pageOf";

describe("pageOf", () => {
  const rows = ["a", "b", "c"];

  it.each([
    {
      cursor: undefined,
      label: "a list shorter than the limit fits on one page",
      limit: 4,
      page: { nextCursor: null, rows: ["a", "b", "c"] },
    },
    {
      cursor: undefined,
      label: "a list exactly at the limit has no next page",
      limit: 3,
      page: { nextCursor: null, rows: ["a", "b", "c"] },
    },
    {
      cursor: undefined,
      label: "a list one past the limit offers the next page",
      limit: 2,
      page: { nextCursor: "2", rows: ["a", "b"] },
    },
    {
      cursor: "2",
      label: "the next page starts at the cursor",
      limit: 2,
      page: { nextCursor: null, rows: ["c"] },
    },
    {
      cursor: "4",
      label: "a cursor past the end reads an empty page",
      limit: 2,
      page: { nextCursor: null, rows: [] },
    },
  ] as const)("$label", ({ cursor, limit, page }) => {
    expect(pageOf(rows, cursor, limit)).toEqual(page);
  });
});
