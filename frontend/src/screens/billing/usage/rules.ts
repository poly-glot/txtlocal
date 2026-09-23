import type { Product, UsageTabRow } from "@/api/generated/dashboard";

import { priceText, productLabel, usernameOf } from "../rules";

export interface UsageFilterState {
  product: Product | "";
  userId: string;
}

export function filteredUsageRows(
  rows: readonly UsageTabRow[],
  filters: UsageFilterState,
): UsageTabRow[] {
  return rows.filter(
    (row) =>
      (filters.product === "" || row.product === filters.product) &&
      (filters.userId === "" || row.userId === filters.userId),
  );
}

export function currentMonthValue(now: Date): string {
  return `${String(now.getFullYear())}-${String(now.getMonth() + 1).padStart(2, "0")}`;
}

export function formatMonthColumn(month: string): string {
  const [year, monthNumber] = month.split("-");

  return `${monthNumber ?? ""}/${year ?? ""}`;
}

function csvField(value: string): string {
  return /[",\n]/.test(value) ? `"${value.replace(/"/g, '""')}"` : value;
}

function csvLine(fields: readonly string[]): string {
  return fields.map(csvField).join(",");
}

export function usageCsv(
  rows: readonly UsageTabRow[],
  lookup: ReadonlyMap<string, string>,
): string {
  const lines = rows.map((row) =>
    csvLine([
      formatMonthColumn(row.month),
      productLabel(row.product),
      usernameOf(lookup, row.userId),
      String(row.quantity),
      priceText(row.costMicro),
    ]),
  );

  return [csvLine(["DATE", "PRODUCT", "USERNAME", "QUANTITY", "COST"]), ...lines].join("\n");
}
