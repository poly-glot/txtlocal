import { describe, expect, it } from "vitest";

import { SCHEDULED } from "@/test/fixtures/campaigns";

import { draftOf, scheduleLabel, scheduleRequestOf } from "./rules";

const NOW = new Date("2026-09-19T12:00:00Z");

const TIMEZONE = "Europe/London";

describe("scheduleLabel", () => {
  it("names the moment a campaign sends now", () => {
    expect(scheduleLabel("", NOW, TIMEZONE)).toBe("Now");
  });

  it("names the date and how far ahead it is", () => {
    expect(scheduleLabel("2027-07-31T22:59:00Z", NOW, TIMEZONE)).toBe("31 Jul 2027 (in 10 months)");
  });

  it("names minutes when the send is within the hour", () => {
    expect(scheduleLabel("2026-09-19T12:30:00Z", NOW, TIMEZONE)).toBe(
      "19 Sept 2026 (in 30 minutes)",
    );
  });
});

describe("scheduleRequestOf", () => {
  it("asks for now when no time was picked", () => {
    expect(scheduleRequestOf("")).toEqual({ now: true });
  });

  it("sends the picked time as an instant", () => {
    expect(scheduleRequestOf("2027-07-31T23:59:00Z")).toEqual({
      now: false,
      sendAt: "2027-07-31T23:59:00.000Z",
    });
  });
});

describe("draftOf", () => {
  it("carries an existing campaign into the editor", () => {
    expect(draftOf(SCHEDULED, "SMS")).toEqual({
      body: SCHEDULED.body,
      footer: SCHEDULED.footer,
      listId: SCHEDULED.listId,
      mediaKey: null,
      name: SCHEDULED.name,
      optOutMode: "REPLY_STOP",
      product: "SMS",
      senderId: SCHEDULED.senderId,
      shortenUrls: false,
      subject: null,
    });
  });

  it("starts a new campaign on the screen's product", () => {
    expect(draftOf(undefined, "MMS").product).toBe("MMS");
  });
});
