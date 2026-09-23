import { describe, expect, it } from "vitest";

import {
  countryFlag,
  countryLabel,
  defaultReportingRange,
  formatDay,
  reportingFilterQuery,
  reportingQueryOf,
} from "./rules";

describe("formatDay", () => {
  it("shows a YYYY-MM-DD day as DD/MM/YYYY", () => {
    expect(formatDay("2026-09-19")).toBe("19/09/2026");
  });
});

describe("countryFlag", () => {
  it.each([
    { iso: "GB", label: "uppercase code", text: "🇬🇧" },
    { iso: "us", label: "lowercase code", text: "🇺🇸" },
  ] as const)("$label", ({ iso, text }) => {
    expect(countryFlag(iso)).toBe(text);
  });
});

describe("countryLabel", () => {
  it("combines the flag with the English region name", () => {
    expect(countryLabel("GB")).toBe("🇬🇧 United Kingdom");
  });
});

describe("defaultReportingRange", () => {
  it("spans from the first of the month two months back through today", () => {
    expect(defaultReportingRange(new Date(2026, 8, 19))).toEqual({
      since: "2026-07-01",
      until: "2026-09-19",
    });
  });

  it("rolls back over a year boundary", () => {
    expect(defaultReportingRange(new Date(2026, 0, 15))).toEqual({
      since: "2025-11-01",
      until: "2026-01-15",
    });
  });
});

describe("reportingFilterQuery and reportingQueryOf", () => {
  const filters = {
    countries: "",
    products: "" as const,
    senderIds: "",
    since: "2026-07-01",
    until: "2026-09-19",
    userIds: "",
  };

  it("omits every unset filter as an empty array", () => {
    expect(reportingFilterQuery(filters)).toEqual({
      countries: [],
      products: [],
      senderIds: [],
      since: "2026-07-01",
      until: "2026-09-19",
      userIds: [],
    });
  });

  it("wraps a set filter in a single-element array", () => {
    expect(
      reportingFilterQuery({ ...filters, countries: "GB", products: "SMS", userIds: "user-1" }),
    ).toEqual({
      countries: ["GB"],
      products: ["SMS"],
      senderIds: [],
      since: "2026-07-01",
      until: "2026-09-19",
      userIds: ["user-1"],
    });
  });

  it("adds the page and page size for the paged query", () => {
    expect(reportingQueryOf(filters, 2, 25)).toEqual({
      countries: [],
      page: 2,
      pageSize: 25,
      products: [],
      senderIds: [],
      since: "2026-07-01",
      until: "2026-09-19",
      userIds: [],
    });
  });
});
