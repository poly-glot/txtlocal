import { describe, expect, it } from "vitest";

import { partsOption, partsOptions } from "./rules";

describe("partsOption", () => {
  it.each([
    { label: "one part is 160 characters", parts: 1, text: "1 = 160 characters" },
    { label: "two parts are 306 characters", parts: 2, text: "2 = 306 characters" },
    { label: "eight parts are 1224 characters", parts: 8, text: "8 = 1224 characters" },
  ] as const)("$label", ({ parts, text }) => {
    expect(partsOption(parts)).toEqual({ label: text, value: String(parts) });
  });

  it("offers one to eight parts", () => {
    expect(partsOptions().map((option) => option.value)).toEqual([
      "1",
      "2",
      "3",
      "4",
      "5",
      "6",
      "7",
      "8",
    ]);
  });
});
