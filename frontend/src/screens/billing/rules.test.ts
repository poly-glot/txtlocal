import { describe, expect, it } from "vitest";

import type { UserRow } from "@/api/generated/dashboard";

import {
  numericSortKey,
  priceText,
  productFilterOf,
  productLabel,
  userOptions,
  usernameLookup,
  usernameOf,
} from "./rules";

describe("productFilterOf", () => {
  it.each([
    { label: "SMS", text: "SMS", value: "SMS" },
    { label: "MMS", text: "MMS", value: "MMS" },
    { label: "MMS as link", text: "MMS_AS_LINK", value: "MMS_AS_LINK" },
    { label: "unknown value falls back to all", text: "bogus", value: "" },
  ] as const)("$label", ({ text, value }) => {
    expect(productFilterOf(text)).toBe(value);
  });
});

describe("productLabel", () => {
  it.each([
    { label: "SMS stays SMS", product: "SMS", text: "SMS" },
    { label: "MMS stays MMS", product: "MMS", text: "MMS" },
    { label: "MMS as link shows as SMS", product: "MMS_AS_LINK", text: "SMS" },
  ] as const)("$label", ({ product, text }) => {
    expect(productLabel(product)).toBe(text);
  });
});

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

describe("usernameLookup and usernameOf", () => {
  const lookup = usernameLookup([
    accountUser("user-1", "demo@txtlocal.local"),
    accountUser("user-2", "sub@txtlocal.local"),
  ]);

  it("resolves a known user id to its username", () => {
    expect(usernameOf(lookup, "user-1")).toBe("demo@txtlocal.local");
  });

  it("falls back to the raw id for an unknown user", () => {
    expect(usernameOf(lookup, "user-9")).toBe("user-9");
  });
});

describe("userOptions", () => {
  it("lists an all-subaccounts option first, then usernames sorted alphabetically", () => {
    const options = userOptions([
      accountUser("user-2", "sub@txtlocal.local"),
      accountUser("user-1", "demo@txtlocal.local"),
    ]);

    expect(options).toEqual([
      { label: "All subaccounts", value: "" },
      { label: "demo@txtlocal.local", value: "user-1" },
      { label: "sub@txtlocal.local", value: "user-2" },
    ]);
  });
});

describe("numericSortKey", () => {
  it.each([{ label: "single digits order correctly", left: 9, right: 10 }] as const)(
    "$label",
    ({ left, right }) => {
      expect(numericSortKey(left) < numericSortKey(right)).toBe(true);
    },
  );
});

describe("priceText", () => {
  it.each([
    { label: "keeps four places for a unit price", micro: 42_700, text: "0.0427" },
    { label: "keeps at least two places", micro: 100_000, text: "0.10" },
    { label: "trims a trailing zero to three places", micro: 123_000, text: "0.123" },
    { label: "shows whole pounds with two places", micro: 1_000_000, text: "1.00" },
    { label: "rounds 49 micro down to nothing", micro: 49, text: "0.00" },
    { label: "rounds 50 micro up to the fourth place", micro: 50, text: "0.0001" },
    { label: "shows nothing as zero", micro: 0, text: "0.00" },
  ] as const)("$label", ({ micro, text }) => {
    expect(priceText(micro)).toBe(text);
  });
});
