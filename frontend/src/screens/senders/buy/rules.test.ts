import { describe, expect, it } from "vitest";

import { defaultNumberFilters, isUseFor, pageNumbers } from "./rules";

describe("isUseFor", () => {
  it.each([
    { label: "accepts a listed option", value: "SMS_MMS", want: true },
    { label: "refuses an unlisted value", value: "VOICE", want: false },
  ] as const)("$label", ({ value, want }) => {
    expect(isUseFor(value)).toBe(want);
  });
});

describe("defaultNumberFilters", () => {
  it("starts with no substring filter and SMS as the use for", () => {
    expect(defaultNumberFilters("GB")).toEqual({ contains: "", country: "GB", useFor: "SMS" });
  });
});

describe("pageNumbers", () => {
  it.each([
    { label: "one page", total: 1, want: [1] },
    { label: "four pages", total: 4, want: [1, 2, 3, 4] },
  ] as const)("$label", ({ total, want }) => {
    expect(pageNumbers(total)).toEqual(want);
  });
});
