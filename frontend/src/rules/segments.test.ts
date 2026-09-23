import { describe, expect, it } from "vitest";

import { MAX_PARTS, segmentSummary, segmentsOf } from "@/rules/segments";

describe("segmentsOf", () => {
  it.each([
    { body: "", encoding: "GSM-7", label: "an empty body is one empty part", length: 0, parts: 1 },
    { body: "Hello", encoding: "GSM-7", label: "plain text is GSM-7", length: 5, parts: 1 },
    {
      body: "a".repeat(160),
      encoding: "GSM-7",
      label: "160 GSM characters fit one part",
      length: 160,
      parts: 1,
    },
    {
      body: "a".repeat(161),
      encoding: "GSM-7",
      label: "161 GSM characters need two parts",
      length: 161,
      parts: 2,
    },
    {
      body: "a".repeat(306),
      encoding: "GSM-7",
      label: "306 GSM characters fit two parts",
      length: 306,
      parts: 2,
    },
    {
      body: "a".repeat(307),
      encoding: "GSM-7",
      label: "307 GSM characters need three parts",
      length: 307,
      parts: 3,
    },
    {
      body: "€",
      encoding: "GSM-7",
      label: "an extension character costs two septets",
      length: 2,
      parts: 1,
    },
    {
      body: "α".repeat(70),
      encoding: "UCS-2",
      label: "70 UCS-2 characters fit one part",
      length: 70,
      parts: 1,
    },
    {
      body: "α".repeat(71),
      encoding: "UCS-2",
      label: "71 UCS-2 characters need two parts",
      length: 71,
      parts: 2,
    },
    {
      body: "Hi 😀",
      encoding: "UCS-2",
      label: "an emoji counts as two UTF-16 units",
      length: 5,
      parts: 1,
    },
    {
      body: "a".repeat(1224),
      encoding: "GSM-7",
      label: "1,224 GSM characters is the last accepted length",
      length: 1224,
      parts: 8,
    },
    {
      body: "a".repeat(1225),
      encoding: "GSM-7",
      label: "1,225 GSM characters is the first refused length",
      length: 1225,
      parts: 9,
    },
  ] as const)("$label", ({ body, encoding, length, parts }) => {
    expect(segmentsOf(body)).toEqual({ encoding, length, parts });
  });

  it("the ceiling is eight parts", () => {
    expect(segmentsOf("a".repeat(1224)).parts).toBe(MAX_PARTS);
    expect(segmentsOf("a".repeat(1225)).parts).toBeGreaterThan(MAX_PARTS);
  });
});

describe("segmentSummary", () => {
  it.each([
    {
      body: "",
      label: "an empty body is nought characters in one part",
      summary: "Approx. 0 characters/1 SMS per recipient.",
    },
    {
      body: "Hello",
      label: "five characters are one part",
      summary: "Approx. 5 characters/1 SMS per recipient.",
    },
    {
      body: "a".repeat(161),
      label: "161 characters are two parts",
      summary: "Approx. 161 characters/2 SMS per recipient.",
    },
  ] as const)("$label", ({ body, summary }) => {
    expect(segmentSummary(segmentsOf(body))).toBe(summary);
  });
});
