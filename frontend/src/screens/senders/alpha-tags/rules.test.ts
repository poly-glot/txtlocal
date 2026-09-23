import { describe, expect, it } from "vitest";

import {
  alphaBadgeTone,
  emptyAlphaTag,
  isUseCase,
  isValidAlphaTag,
  labelForUseCase,
  registeredText,
} from "./rules";

describe("isValidAlphaTag", () => {
  it.each([
    { label: "refuses two characters", tag: "TX", want: false },
    { label: "accepts three characters", tag: "TXT", want: true },
    { label: "accepts eleven characters", tag: "TXTLOCAL123", want: true },
    { label: "refuses twelve characters", tag: "TXTLOCAL1234", want: false },
    { label: "refuses a space", tag: "TXT LOCAL", want: false },
    { label: "refuses a hyphen", tag: "TXT-LOCAL", want: false },
    { label: "accepts a plus", tag: "TXT+LOCAL", want: true },
  ] as const)("$label", ({ tag, want }) => {
    expect(isValidAlphaTag(tag)).toBe(want);
  });
});

describe("isUseCase", () => {
  it.each([
    { label: "accepts a listed use case", value: "MARKETING", want: true },
    { label: "refuses an unlisted value", value: "SPAM", want: false },
  ] as const)("$label", ({ value, want }) => {
    expect(isUseCase(value)).toBe(want);
  });
});

describe("labelForUseCase", () => {
  it("names the two-factor authentication use case in full", () => {
    expect(labelForUseCase("TWO_FACTOR_AUTHENTICATION")).toBe("Two-factor authentication");
  });

  it("falls back to the raw value for an unlisted use case", () => {
    expect(labelForUseCase("SPAM")).toBe("SPAM");
  });
});

describe("emptyAlphaTag", () => {
  it("starts blank with the given country and Marketing as the use case", () => {
    expect(emptyAlphaTag("GB")).toEqual({ country: "GB", tag: "", useCase: "MARKETING" });
  });
});

describe("alphaBadgeTone", () => {
  it.each([
    { label: "ready is success", status: "READY", want: "success" },
    { label: "under review is warning", status: "UNDER_REVIEW", want: "warning" },
    { label: "rejected is danger", status: "REJECTED", want: "danger" },
  ] as const)("$label", ({ status, want }) => {
    expect(alphaBadgeTone(status)).toBe(want);
  });
});

describe("registeredText", () => {
  it("formats the registration date", () => {
    expect(registeredText("2026-09-19T12:00:00Z")).toBe("19 Sept 2026");
  });
});
