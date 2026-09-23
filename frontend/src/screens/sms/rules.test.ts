import { describe, expect, it } from "vitest";

import { OVERVIEW } from "@/test/fixtures/senders";

import { earliestSendAt, latestSendAt, senderDisplayOf } from "./rules";

describe("senderDisplayOf", () => {
  it("names the chosen sender", () => {
    expect(senderDisplayOf(OVERVIEW, "sender-shared")).toBe("Shared Number");
  });

  it("falls back to Smart Senders when none was chosen", () => {
    expect(senderDisplayOf(OVERVIEW, "")).toBe("Smart Senders");
  });
});

describe("earliestSendAt", () => {
  it("is five minutes after now", () => {
    expect(earliestSendAt(new Date(2026, 8, 19, 9, 0))).toEqual(new Date(2026, 8, 19, 9, 5));
  });
});

describe("latestSendAt", () => {
  it("is twelve months after now", () => {
    expect(latestSendAt(new Date(2026, 8, 19, 9, 0))).toEqual(new Date(2027, 8, 19, 9, 0));
  });
});
