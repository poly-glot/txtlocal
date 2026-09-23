import { describe, expect, it } from "vitest";

import { cardExpiry } from "./rules";

describe("cardExpiry", () => {
  it.each([
    { expMonth: 12, expYear: 2035, label: "double-digit month and year", text: "12/35" },
    { expMonth: 3, expYear: 2027, label: "single-digit month is zero-padded", text: "03/27" },
  ] as const)("$label", ({ expMonth, expYear, text }) => {
    expect(cardExpiry(expMonth, expYear)).toBe(text);
  });
});
