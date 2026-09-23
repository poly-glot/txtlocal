import type { Sort } from "./Table";

export function toggleSort(sort: Sort, key: string): Sort {
  if (sort.key !== key) {
    return { direction: "asc", key };
  }

  return { direction: sort.direction === "asc" ? "desc" : "asc", key };
}

export function sortRows<Row>(
  rows: readonly Row[],
  sort: Sort,
  valueOf: (row: Row, key: string) => string,
): Row[] {
  const direction = sort.direction === "asc" ? 1 : -1;

  return [...rows].sort(
    (left, right) => direction * valueOf(left, sort.key).localeCompare(valueOf(right, sort.key)),
  );
}

export function ariaSortOf(
  key: string,
  sort: Sort | undefined,
): "ascending" | "descending" | undefined {
  if (sort?.key !== key) {
    return undefined;
  }

  return sort.direction === "asc" ? "ascending" : "descending";
}
