import { describe, expect, it } from "vitest";

import { DELIVERY_RULE } from "@/test/fixtures/automation";

import { isHttpsUrl, toggledDeliveryRule } from "./rules";

describe("isHttpsUrl", () => {
  it.each([
    { label: "an https URL is valid", url: "https://example.com/hook", valid: true },
    { label: "an http URL is rejected", url: "http://example.com/hook", valid: false },
    { label: "bare https:// with nothing after is rejected", url: "https://", valid: false },
    { label: "an empty string is rejected", url: "", valid: false },
  ] as const)("$label", ({ url, valid }) => {
    expect(isHttpsUrl(url)).toBe(valid);
  });
});

describe("toggledDeliveryRule", () => {
  it.each([
    { enabled: true, expected: false, label: "an enabled rule is sent disabled" },
    { enabled: false, expected: true, label: "a disabled rule is sent enabled" },
  ] as const)("$label", ({ enabled, expected }) => {
    expect(toggledDeliveryRule({ ...DELIVERY_RULE, enabled })).toEqual({
      input: {
        enabled: expected,
        events: "ALL",
        name: "Order updates",
        url: "https://example.com/webhook",
      },
      ruleId: "delivery-1",
    });
  });
});
