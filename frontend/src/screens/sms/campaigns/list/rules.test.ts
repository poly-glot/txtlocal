import { describe, expect, it } from "vitest";

import { addFirstLabel, campaignsHeading } from "./rules";

describe("copy for a product", () => {
  it.each([
    { label: "the SMS heading", product: "SMS", text: "SMS Campaigns" },
    { label: "the MMS heading", product: "MMS", text: "MMS Campaigns" },
  ] as const)("$label", ({ product, text }) => {
    expect(campaignsHeading(product)).toBe(text);
  });

  it.each([
    {
      label: "the SMS empty-state button",
      product: "SMS",
      text: "CLICK HERE TO ADD YOUR FIRST SMS CAMPAIGN",
    },
    {
      label: "the MMS empty-state button",
      product: "MMS",
      text: "CLICK HERE TO ADD YOUR FIRST MMS CAMPAIGN",
    },
  ] as const)("$label", ({ product, text }) => {
    expect(addFirstLabel(product)).toBe(text);
  });
});
