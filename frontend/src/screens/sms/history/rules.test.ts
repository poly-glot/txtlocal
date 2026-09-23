import { describe, expect, it } from "vitest";

import { historyTitle, initialHistoryFilters, presetRange } from "./rules";

describe("presetRange", () => {
  const today = new Date("2026-09-19T12:00:00Z");

  it.each([
    { from: "2026-09-19", label: "Today is one day", preset: "Today", to: "2026-09-19" },
    {
      from: "2026-09-12",
      label: "Last 7 days ends today",
      preset: "Last 7 days",
      to: "2026-09-19",
    },
    {
      from: "2026-08-20",
      label: "Last 30 days ends today",
      preset: "Last 30 days",
      to: "2026-09-19",
    },
  ] as const)("$label", ({ from, preset, to }) => {
    expect(presetRange(preset, today)).toEqual({ from, to });
  });
});

describe("historyTitle", () => {
  it.each([
    { kind: "SMS", label: "the SMS heading", title: "SMS History" },
    { kind: "MMS", label: "the MMS heading", title: "MMS History" },
  ] as const)("$label", ({ kind, title }) => {
    expect(historyTitle(kind)).toBe(title);
  });
});

describe("initialHistoryFilters", () => {
  it("filters SMS history with no kind restriction", () => {
    expect(initialHistoryFilters("SMS")).toEqual({ field: "TO" });
  });

  it("filters MMS history to the MMS kind", () => {
    expect(initialHistoryFilters("MMS")).toEqual({ field: "TO", kind: "MMS" });
  });
});
