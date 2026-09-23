import { describe, expect, it } from "vitest";

import { ariaSortOf, sortRows, toggleSort } from "./sort";

describe("ariaSortOf", () => {
  it.each([
    { expected: undefined, key: "date", label: "an unsorted column", sort: undefined },
    {
      expected: undefined,
      key: "name",
      label: "another column",
      sort: { direction: "asc", key: "date" },
    },
    {
      expected: "ascending",
      key: "date",
      label: "ascending",
      sort: { direction: "asc", key: "date" },
    },
    {
      expected: "descending",
      key: "date",
      label: "descending",
      sort: { direction: "desc", key: "date" },
    },
  ] as const)("$label", ({ expected, key, sort }) => {
    expect(ariaSortOf(key, sort)).toBe(expected);
  });
});

describe("toggleSort", () => {
  it.each([
    {
      expected: { direction: "asc", key: "name" },
      key: "name",
      label: "a new column starts ascending",
    },
    { expected: { direction: "asc", key: "date" }, key: "date", label: "the same column flips" },
  ] as const)("$label", ({ expected, key }) => {
    expect(toggleSort({ direction: "desc", key: "date" }, key)).toEqual(expected);
  });
});

describe("sortRows", () => {
  it("orders rows by the value of the sorted key", () => {
    const rows = [{ name: "b" }, { name: "a" }];

    expect(sortRows(rows, { direction: "asc", key: "name" }, (row) => row.name)).toEqual([
      { name: "a" },
      { name: "b" },
    ]);
  });
});
