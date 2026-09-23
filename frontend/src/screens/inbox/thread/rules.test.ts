import { describe, expect, it } from "vitest";

import { chronological, defaultSenderId, senderIdOf, toggleStatusLabel } from "./rules";

describe("toggleStatusLabel", () => {
  it.each([
    {
      label: "an open conversation offers to close it",
      status: "OPEN",
      value: "Close conversation",
    },
    {
      label: "a closed conversation offers to reopen it",
      status: "CLOSED",
      value: "Reopen conversation",
    },
  ] as const)("$label", ({ status, value }) => {
    expect(toggleStatusLabel(status)).toBe(value);
  });
});

describe("chronological", () => {
  it("reverses a newest-first page into oldest-first order", () => {
    expect(chronological([3, 2, 1])).toEqual([1, 2, 3]);
  });

  it("leaves the source array untouched", () => {
    const items = [3, 2, 1];
    chronological(items);

    expect(items).toEqual([3, 2, 1]);
  });
});

describe("defaultSenderId", () => {
  it.each([
    { input: "sender-own-1", label: "a known sender is kept", output: "sender-own-1" },
    { input: null, label: "null falls back to the shared sender", output: "" },
    { input: undefined, label: "undefined falls back to the shared sender", output: "" },
  ] as const)("$label", ({ input, output }) => {
    expect(defaultSenderId(input)).toBe(output);
  });
});

describe("senderIdOf", () => {
  it.each([
    { choice: "sender-own-1", label: "a chosen sender is sent as itself", output: "sender-own-1" },
    { choice: "", label: "Smart Senders is sent as no sender", output: null },
  ] as const)("$label", ({ choice, output }) => {
    expect(senderIdOf(choice)).toBe(output);
  });
});
