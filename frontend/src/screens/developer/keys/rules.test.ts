import { describe, expect, it } from "vitest";

import { OWNER_ROW, SUB_ROW } from "@/test/fixtures/identity";

import { sortSubaccounts, toNewSubaccount } from "./rules";

describe("toNewSubaccount", () => {
  it("omits the notes and phone that were left blank", () => {
    expect(
      toNewSubaccount({ firstName: "Sam", lastName: "", notes: "", phone: "", username: "s@x.io" }),
    ).toEqual({ firstName: "Sam", lastName: "", username: "s@x.io" });
  });

  it("keeps the optional fields that were filled", () => {
    expect(
      toNewSubaccount({
        firstName: "Sam",
        lastName: "Patel",
        notes: "Support",
        phone: "+447700900105",
        username: "s@x.io",
      }),
    ).toEqual({
      firstName: "Sam",
      lastName: "Patel",
      notes: "Support",
      phone: "+447700900105",
      username: "s@x.io",
    });
  });
});

describe("sortSubaccounts", () => {
  it("orders by username ascending", () => {
    const rows = sortSubaccounts([SUB_ROW, OWNER_ROW], { direction: "asc", key: "username" });

    expect(rows.map((row) => row.username)).toEqual(["demo@txtlocal.local", "sub@txtlocal.local"]);
  });

  it("orders by notes descending with blanks last", () => {
    const rows = sortSubaccounts([OWNER_ROW, SUB_ROW], { direction: "desc", key: "notes" });

    expect(rows.map((row) => row.userId)).toEqual(["user-2", "user-1"]);
  });
});
