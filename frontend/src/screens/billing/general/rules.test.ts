import { describe, expect, it } from "vitest";

import { optionsWithSaved } from "./rules";

describe("optionsWithSaved", () => {
  const options = [
    { label: "£10", value: "10000000" },
    { label: "£30", value: "30000000" },
  ];

  it.each([
    {
      expected: [
        { label: "£10", value: "10000000" },
        { label: "£30", value: "30000000" },
      ],
      label: "keeps the choices when the saved amount is one of them",
      savedMicro: 30_000_000,
    },
    {
      expected: [
        { label: "£10", value: "10000000" },
        { label: "£20.00", value: "20000000" },
        { label: "£30", value: "30000000" },
      ],
      label: "adds a saved amount that is no longer a choice, in order",
      savedMicro: 20_000_000,
    },
  ] as const)("$label", ({ expected, savedMicro }) => {
    expect(optionsWithSaved(options, savedMicro)).toEqual(expected);
  });
});
