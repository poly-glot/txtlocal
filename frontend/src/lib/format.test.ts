import { describe, expect, it } from "vitest";

import { dateTimeIn, minuteValue } from "./format";

describe("minuteValue", () => {
  it.each([
    {
      date: new Date(2026, 8, 19, 9, 5),
      label: "pads the month, day, hour and minute",
      value: "2026-09-19T09:05",
    },
    {
      date: new Date(2026, 11, 31, 23, 59),
      label: "keeps the last minute of the year",
      value: "2026-12-31T23:59",
    },
  ] as const)("$label", ({ date, value }) => {
    expect(minuteValue(date)).toBe(value);
  });
});

describe("dateTimeIn", () => {
  it.each([
    {
      label: "London is one hour ahead of UTC in September",
      timezone: "Europe/London",
      value: "19/09/2026, 15:13",
    },
    { label: "UTC is the stored instant", timezone: "UTC", value: "19/09/2026, 14:13" },
  ] as const)("$label", ({ timezone, value }) => {
    expect(dateTimeIn("2026-09-19T14:13:44Z", timezone, "short")).toBe(value);
  });
});
