import { describe, expect, it } from "vitest";

import { EXAMPLE_LIST, OPT_OUT_LIST } from "@/test/fixtures/contacts";

import { emptyDraft } from "../rules";
import {
  contentTitle,
  counterText,
  footerFor,
  isMessageComplete,
  listSummary,
  sendableLists,
  senderTitle,
} from "./rules";

const smsDraft = (body: string, footer = "") => ({ ...emptyDraft("SMS"), body, footer });

describe("counterText", () => {
  it("writes the SMS counter from the body", () => {
    expect(counterText(smsDraft("Hello"), "SMS")).toBe("Approx. 5 characters/1 SMS per recipient.");
  });

  it("counts the footer toward the SMS length", () => {
    expect(counterText(smsDraft("Hello", "Reply STOP to opt-out"), "SMS")).toBe(
      "Approx. 27 characters/1 SMS per recipient.",
    );
  });

  it("writes the MMS counter whatever the body", () => {
    expect(counterText(smsDraft("Hello"), "MMS")).toBe("1 MMS per recipient.");
  });
});

describe("completion", () => {
  it.each([
    { body: "", complete: false, label: "an empty body is not complete" },
    { body: "   ", complete: false, label: "blank space is not complete" },
    { body: "Hello", complete: true, label: "a written body is complete" },
  ] as const)("$label", ({ body, complete }) => {
    expect(isMessageComplete(smsDraft(body), "SMS")).toBe(complete);
  });

  it.each([
    { complete: false, label: "an MMS draft with no media is not complete", mediaKey: null },
    { complete: true, label: "an MMS draft with media is complete", mediaKey: "media-1" },
  ] as const)("$label", ({ complete, mediaKey }) => {
    expect(isMessageComplete({ ...emptyDraft("MMS"), mediaKey }, "MMS")).toBe(complete);
  });
});

describe("copy for a product", () => {
  it.each([
    { label: "the SMS content title", product: "SMS", text: "Your SMS Content" },
    { label: "the MMS content title", product: "MMS", text: "Your MMS Content" },
  ] as const)("$label", ({ product, text }) => {
    expect(contentTitle(product)).toBe(text);
  });

  it.each([
    { label: "the SMS sender title", product: "SMS", text: "Select your Sender ID" },
    { label: "the MMS sender title", product: "MMS", text: "Your Sender Details" },
  ] as const)("$label", ({ product, text }) => {
    expect(senderTitle(product)).toBe(text);
  });
});

describe("the opt-out footer", () => {
  it.each([
    {
      label: "Reply STOP keeps the stop sentence",
      mode: "REPLY_STOP",
      text: "Reply STOP to opt-out",
    },
    {
      label: "Unsubscribe Link holds the link placeholder",
      mode: "UNSUBSCRIBE_LINK",
      text: "Unsubscribe: {unsubscribe_link}",
    },
  ] as const)("$label", ({ mode, text }) => {
    expect(footerFor(mode)).toBe(text);
  });
});

describe("lists", () => {
  it("summarises a chosen list by name and size", () => {
    expect(listSummary(EXAMPLE_LIST)).toBe("Example List 2 recipient(s)");
  });

  it("keeps the opt-out list out of the campaign choices", () => {
    expect(sendableLists([EXAMPLE_LIST, OPT_OUT_LIST])).toEqual([EXAMPLE_LIST]);
  });
});
