import { describe, expect, it } from "vitest";

import type { UsageTabRow, UserRow } from "@/api/generated/dashboard";

import { usernameLookup } from "../rules";
import { currentMonthValue, filteredUsageRows, formatMonthColumn, usageCsv } from "./rules";

function accountUser(userId: string, username: string): UserRow {
  return {
    apiKeyPrefix: "aaaaaaaa",
    createdAt: "2026-09-19T10:00:00Z",
    firstName: "",
    lastName: "",
    notes: null,
    phone: null,
    role: "SUB",
    status: "ACTIVE",
    userId,
    username,
  };
}

describe("currentMonthValue", () => {
  it("formats the year and month with a zero-padded month", () => {
    expect(currentMonthValue(new Date(2026, 8, 19))).toBe("2026-09");
  });
});

describe("formatMonthColumn", () => {
  it("shows a YYYY-MM month as MM/YYYY", () => {
    expect(formatMonthColumn("2026-09")).toBe("09/2026");
  });
});

describe("filteredUsageRows", () => {
  const rows: UsageTabRow[] = [
    { costMicro: 42_700, month: "2026-09", product: "SMS", quantity: 1, userId: "user-1" },
    { costMicro: 85_400, month: "2026-09", product: "MMS", quantity: 2, userId: "user-2" },
  ];

  it("returns every row when no filter is set", () => {
    expect(filteredUsageRows(rows, { product: "", userId: "" })).toHaveLength(2);
  });

  it("filters by product", () => {
    expect(filteredUsageRows(rows, { product: "MMS", userId: "" })).toEqual([rows[1]]);
  });

  it("filters by user", () => {
    expect(filteredUsageRows(rows, { product: "", userId: "user-1" })).toEqual([rows[0]]);
  });
});

describe("usageCsv", () => {
  it("builds a header row and one row per usage line", () => {
    const rows: UsageTabRow[] = [
      {
        costMicro: 42_700,
        month: "2026-09",
        product: "MMS_AS_LINK",
        quantity: 1,
        userId: "user-1",
      },
    ];
    const lookup = usernameLookup([accountUser("user-1", "demo@txtlocal.local")]);

    expect(usageCsv(rows, lookup)).toBe(
      "DATE,PRODUCT,USERNAME,QUANTITY,COST\n09/2026,SMS,demo@txtlocal.local,1,0.0427",
    );
  });
});
