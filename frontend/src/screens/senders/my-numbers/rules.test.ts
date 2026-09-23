import { describe, expect, it } from "vitest";

import { DEDICATED_SENDER, OWN_SENDER, PENDING_SENDER } from "@/test/fixtures/senders";

import {
  dedicatedBadgeTone,
  dialled,
  isAwaitingVerification,
  isCancellableDedicated,
  isDiallable,
  isVerificationCode,
  lastVerifiedText,
  reverifyDraft,
} from "./rules";

describe("isDiallable", () => {
  it.each([
    { label: "refuses six digits", number: "074001", want: false },
    { label: "accepts seven digits", number: "0740012", want: true },
    { label: "ignores spaces and brackets", number: "(074) 00 1", want: false },
    { label: "accepts a full national number", number: "07400 123 123", want: true },
    { label: "refuses letters alone", number: "abcdefgh", want: false },
  ] as const)("$label", ({ number, want }) => {
    expect(isDiallable(number)).toBe(want);
  });
});

describe("isVerificationCode", () => {
  it.each([
    { code: "12345", label: "refuses five digits", want: false },
    { code: "123456", label: "accepts six digits", want: true },
    { code: "1234567", label: "refuses seven digits", want: false },
    { code: "12a456", label: "refuses a letter among six characters", want: false },
    { code: "000000", label: "accepts the fake-mode code", want: true },
  ] as const)("$label", ({ code, want }) => {
    expect(isVerificationCode(code)).toBe(want);
  });
});

describe("dialled", () => {
  it.each([
    { country: "GB", label: "drops the trunk zero", number: "07400123123", want: "+447400123123" },
    {
      country: "GB",
      label: "keeps an E.164 number",
      number: "+447400123123",
      want: "+447400123123",
    },
    { country: "GB", label: "strips punctuation", number: "07400 123 123", want: "+447400123123" },
    {
      country: "GB",
      label: "reads the 00 prefix",
      number: "00447400123123",
      want: "+447400123123",
    },
    {
      country: "US",
      label: "prefixes the chosen country",
      number: "4155550123",
      want: "+14155550123",
    },
  ] as const)("$label", ({ country, number, want }) => {
    expect(dialled(country, number)).toBe(want);
  });
});

describe("lastVerifiedText", () => {
  it.each([
    { label: "formats a verified date", value: "2026-09-19T12:00:00Z", want: "19 Sept 2026" },
    { label: "shows nothing when never verified", value: null, want: "" },
    { label: "shows nothing when the field is absent", value: undefined, want: "" },
  ] as const)("$label", ({ value, want }) => {
    expect(lastVerifiedText(value)).toBe(want);
  });
});

describe("isAwaitingVerification", () => {
  it("is true for a number whose code was never entered", () => {
    expect(isAwaitingVerification(PENDING_SENDER)).toBe(true);
  });

  it("is false for a verified number", () => {
    expect(isAwaitingVerification(OWN_SENDER)).toBe(false);
  });
});

describe("reverifyDraft", () => {
  it("carries the number and nickname back into the form with an empty code", () => {
    expect(reverifyDraft(PENDING_SENDER)).toEqual({
      code: "",
      country: "GB",
      nickname: "New phone",
      number: "+447400123123",
    });
  });

  it("leaves the nickname blank when the sender has none", () => {
    expect(reverifyDraft({ ...PENDING_SENDER, nickname: null }).nickname).toBe("");
  });
});

describe("isCancellableDedicated", () => {
  it("is true for a ready, uncancelled dedicated number", () => {
    expect(isCancellableDedicated(DEDICATED_SENDER)).toBe(true);
  });

  it("is false once already cancelled", () => {
    expect(isCancellableDedicated({ ...DEDICATED_SENDER, cancelled: true })).toBe(false);
  });

  it("is false once released", () => {
    expect(isCancellableDedicated({ ...DEDICATED_SENDER, status: "RELEASED" })).toBe(false);
  });

  it("is false for a sender that is not dedicated", () => {
    expect(isCancellableDedicated(OWN_SENDER)).toBe(false);
  });
});

describe("dedicatedBadgeTone", () => {
  it.each([
    { label: "ready is success", status: "READY", want: "success" },
    { label: "released is neutral", status: "RELEASED", want: "neutral" },
    { label: "provisioning is warning", status: "PROVISIONING", want: "warning" },
  ] as const)("$label", ({ status, want }) => {
    expect(dedicatedBadgeTone(status)).toBe(want);
  });
});
