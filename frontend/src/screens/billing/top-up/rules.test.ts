import { describe, expect, it } from "vitest";

import { autoRechargeText, estimateText, savingsText } from "./rules";

describe("estimateText", () => {
  it.each([
    {
      country: "GB",
      estimate: 999,
      expected: "~ 999 SMS to United Kingdom",
      label: "below a thousand",
    },
    {
      country: "GB",
      estimate: 1_170,
      expected: "~ 1,170 SMS to United Kingdom",
      label: "groups thousands",
    },
    {
      country: "US",
      estimate: 234,
      expected: "~ 234 SMS to United States",
      label: "names the priced country",
    },
    {
      country: "ZZZ",
      estimate: 234,
      expected: "~ 234 SMS to ZZZ",
      label: "falls back to the code",
    },
  ] as const)("$label", ({ country, estimate, expected }) => {
    expect(estimateText(estimate, country)).toBe(expected);
  });
});

describe("autoRechargeText", () => {
  it.each([
    { autoRecharge: true, expected: "Auto Recharge ON", label: "on" },
    { autoRecharge: false, expected: "Auto Recharge OFF", label: "off" },
  ] as const)("$label", ({ autoRecharge, expected }) => {
    expect(autoRechargeText(autoRecharge)).toBe(expected);
  });
});

describe("savingsText", () => {
  it("shows a savings percentage", () => {
    expect(savingsText(14)).toBe("Save 14%");
  });
});
