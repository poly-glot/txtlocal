import { describe, expect, it } from "vitest";

import type { Draft, Recipient } from "./rules";
import {
  confirmSendTitle,
  deliverLabel,
  emptyDraft,
  isSendable,
  quickSendRequest,
  skippedSummary,
} from "./rules";

const smsDraft = (overrides: Partial<Draft> = {}): Draft => ({
  ...emptyDraft("SMS"),
  ...overrides,
});

const mmsDraft = (overrides: Partial<Draft> = {}): Draft => ({
  ...emptyDraft("MMS"),
  ...overrides,
});

describe("quickSendRequest recipients", () => {
  const chip: Recipient = { kind: "NUMBER", label: "07411972333", value: "07411972333" };
  const list: Recipient = { kind: "LIST", label: "Example List (12)", value: "list-1" };

  it.each([
    { label: "a number alone travels in to", listIds: [], recipients: [chip], to: ["07411972333"] },
    { label: "a list alone travels in listIds", listIds: ["list-1"], recipients: [list], to: [] },
    {
      label: "a mixed selection splits between the two",
      listIds: ["list-1"],
      recipients: [chip, list],
      to: ["07411972333"],
    },
  ] as const)("$label", ({ listIds, recipients, to }) => {
    const request = quickSendRequest(smsDraft({ body: "Hi", recipients: [...recipients] }));

    expect(request.listIds).toEqual(listIds);
    expect(request.to).toEqual(to);
  });
});

describe("skippedSummary", () => {
  it.each([
    { label: "no refusals have no summary", refused: [], summary: undefined },
    {
      label: "one country refusal is counted",
      refused: [
        {
          message: "Sending to FR is not enabled for this account",
          reason: "COUNTRY_NOT_ENABLED",
          to: "+33612345678",
        },
      ],
      summary: "1 recipients skipped (country not enabled)",
    },
    {
      label: "another reason is not counted as a skipped country",
      refused: [
        { message: "This contact has opted out", reason: "OPTED_OUT", to: "+447400123105" },
      ],
      summary: undefined,
    },
  ] as const)("$label", ({ refused, summary }) => {
    expect(skippedSummary(refused)).toBe(summary);
  });
});

describe("deliverLabel", () => {
  it.each([
    { label: "an empty send time is immediate", sendAt: "", value: "Immediately" },
    {
      label: "a chosen time is shown in the account time zone",
      sendAt: "2026-09-19T14:13:44Z",
      value: "19/09/2026, 15:13",
    },
  ] as const)("$label", ({ sendAt, value }) => {
    expect(deliverLabel(sendAt, "Europe/London")).toBe(value);
  });
});

describe("isSendable", () => {
  const chip: Recipient = { kind: "NUMBER", label: "+447400123105", value: "+447400123105" };

  it.each([
    {
      body: "Hello",
      label: "a recipient and a message are enough",
      recipients: [chip],
      sendable: true,
    },
    {
      body: "Hello",
      label: "a message without a recipient is not",
      recipients: [],
      sendable: false,
    },
    { body: "   ", label: "blank text is not a message", recipients: [chip], sendable: false },
  ] as const)("$label", ({ body, recipients, sendable }) => {
    expect(isSendable(smsDraft({ body, recipients: [...recipients] }))).toBe(sendable);
  });

  it.each([
    { label: "an MMS draft with no media is not sendable", mediaKey: null, sendable: false },
    { label: "an MMS draft with media is sendable", mediaKey: "media-1", sendable: true },
  ] as const)("$label", ({ mediaKey, sendable }) => {
    const chip: Recipient = { kind: "NUMBER", label: "+447400123105", value: "+447400123105" };

    expect(isSendable(mmsDraft({ body: "", mediaKey, recipients: [chip] }))).toBe(sendable);
  });
});

describe("quickSendRequest", () => {
  const chip: Recipient = { kind: "NUMBER", label: "07411972333", value: "07411972333" };

  it("sends now as a null send time and no sender", () => {
    expect(
      quickSendRequest(smsDraft({ body: "Hi", recipients: [chip], shortenUrls: true })),
    ).toEqual({
      body: "Hi",
      kind: "SMS",
      listIds: [],
      mediaKey: null,
      messageType: "PROMOTIONAL",
      sendAt: null,
      senderId: null,
      shortenUrls: true,
      subject: "",
      to: ["07411972333"],
    });
  });

  it("sends a chosen local time as an instant", () => {
    const request = quickSendRequest(
      smsDraft({
        body: "Hi",
        recipients: [chip],
        sendAt: "2026-09-19T10:00",
        senderId: "sender-own",
      }),
    );

    expect(request.sendAt).toBe(new Date(2026, 8, 19, 10, 0).toISOString());
    expect(request.senderId).toBe("sender-own");
  });

  it("carries the media key and subject for an MMS draft", () => {
    const request = quickSendRequest(
      mmsDraft({ body: "Hi", mediaKey: "media-1", recipients: [chip], subject: "Sale" }),
    );

    expect(request).toMatchObject({ kind: "MMS", mediaKey: "media-1", subject: "Sale" });
  });
});

describe("confirmSendTitle", () => {
  it.each([
    { kind: "SMS", label: "the SMS title", title: "Confirm SMS Send" },
    { kind: "MMS", label: "the MMS title", title: "Confirm MMS Send" },
  ] as const)("$label", ({ kind, title }) => {
    expect(confirmSendTitle(kind)).toBe(title);
  });
});
