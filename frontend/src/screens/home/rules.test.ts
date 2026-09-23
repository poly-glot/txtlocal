import { describe, expect, it } from "vitest";

import type { QuickSendResult } from "@/api/generated/dashboard";
import { segmentsOf } from "@/rules/segments";
import { SEND_RESULT } from "@/test/fixtures/messaging";

import {
  TEST_SENT_MSG,
  capacityOf,
  counterText,
  recipientsOf,
  testSendNotice,
  testSendRequest,
} from "./rules";

describe("recipientsOf", () => {
  it.each([
    { label: "a single number", recipients: ["+447700900105"], text: "+447700900105" },
    {
      label: "comma-separated numbers are trimmed",
      recipients: ["+447700900105", "07700900100"],
      text: " +447700900105 , 07700900100 ",
    },
    { label: "empty entries are dropped", recipients: ["+447700900105"], text: "+447700900105,," },
    { label: "blank text has no recipients", recipients: [], text: "  " },
  ] as const)("$label", ({ recipients, text }) => {
    expect(recipientsOf(text)).toEqual(recipients);
  });
});

describe("testSendNotice", () => {
  it("confirms a send nobody refused", () => {
    expect(testSendNotice({ data: SEND_RESULT, status: "OK" })).toEqual({
      message: TEST_SENT_MSG,
      tone: "success",
    });
  });

  it("reads out every refusal's sentence, not its code", () => {
    const refused: QuickSendResult["refused"] = [
      { message: "This contact has opted out", reason: "OPTED_OUT", to: "+447700900105" },
      {
        message: "While your account is in trial you can send to your verified numbers only",
        reason: "NOT_VERIFIED",
        to: "+447700900100",
      },
    ];

    expect(testSendNotice({ data: { ...SEND_RESULT, refused }, status: "OK" })).toEqual({
      message:
        "This contact has opted out While your account is in trial you can send to your verified numbers only",
      tone: "error",
    });
  });
});

describe("testSendRequest", () => {
  it("sends an SMS with the server's defaults and no sender", () => {
    expect(testSendRequest("Hello", ["+447700900105"])).toEqual({
      body: "Hello",
      kind: "SMS",
      messageType: "PROMOTIONAL",
      shortenUrls: false,
      subject: "",
      to: ["+447700900105"],
    });
  });
});

describe("capacityOf", () => {
  it.each([
    { capacity: 1224, encoding: "GSM-7", label: "GSM-7 holds 1,224 characters in eight parts" },
    { capacity: 536, encoding: "UCS-2", label: "UCS-2 holds 536 characters in eight parts" },
  ] as const)("$label", ({ capacity, encoding }) => {
    expect(capacityOf(encoding)).toBe(capacity);
  });
});

describe("counterText", () => {
  it.each([
    { body: "Hello", label: "GSM text counts against 1224", text: "5 / 1224" },
    { body: "Привет", label: "UCS-2 text counts against 536", text: "6 / 536" },
  ] as const)("$label", ({ body, text }) => {
    expect(counterText(segmentsOf(body))).toBe(text);
  });
});
