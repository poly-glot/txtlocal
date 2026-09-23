import { describe, expect, it } from "vitest";

import { minuteValue } from "@/lib/format";

import {
  dateRangePresetOf,
  logsQueryOf,
  outcomeParam,
  outcomeTone,
  statusFilterOf,
  windowOf,
} from "./rules";

const NOW = new Date("2026-09-20T12:00:00.000Z");

describe("outcomeParam", () => {
  it.each([
    { label: "All sends no outcome filter", outcome: null, status: "All" },
    { label: "Successful maps to ok", outcome: "ok", status: "Successful" },
    {
      label: "Failed maps to failed only, refused is a known gap",
      outcome: "failed",
      status: "Failed",
    },
  ] as const)("$label", ({ outcome, status }) => {
    expect(outcomeParam(status)).toBe(outcome);
  });
});

describe("outcomeTone", () => {
  it.each([
    { label: "ok is a success tone", outcome: "ok", tone: "success" },
    { label: "refused is a warning tone", outcome: "refused", tone: "warning" },
    { label: "failed is a danger tone", outcome: "failed", tone: "danger" },
    { label: "an unknown outcome is neutral", outcome: "mystery", tone: "neutral" },
  ] as const)("$label", ({ outcome, tone }) => {
    expect(outcomeTone(outcome)).toBe(tone);
  });
});

describe("statusFilterOf", () => {
  it.each([
    { label: "Successful stays Successful", value: "Successful", want: "Successful" },
    { label: "Failed stays Failed", value: "Failed", want: "Failed" },
    { label: "anything else falls back to All", value: "nonsense", want: "All" },
  ] as const)("$label", ({ value, want }) => {
    expect(statusFilterOf(value)).toBe(want);
  });
});

describe("dateRangePresetOf", () => {
  it.each([
    { label: "Last 7 days stays Last 7 days", value: "Last 7 days", want: "Last 7 days" },
    { label: "Custom stays Custom", value: "Custom", want: "Custom" },
    {
      label: "anything else falls back to Last 24 hours",
      value: "nonsense",
      want: "Last 24 hours",
    },
  ] as const)("$label", ({ value, want }) => {
    expect(dateRangePresetOf(value)).toBe(want);
  });
});

describe("windowOf", () => {
  it("Last 24 hours sends no since or until, the server defaults the window", () => {
    const filters = { customFrom: "", customTo: "", preset: "Last 24 hours" } as const;

    expect(windowOf({ ...filters, endpoint: "", status: "All", subaccount: "" }, NOW)).toEqual({
      since: null,
      until: null,
    });
  });

  it("Last 7 days sends the seven days up to now, the widest window the server accepts", () => {
    const filters = { customFrom: "", customTo: "", preset: "Last 7 days" } as const;

    expect(windowOf({ ...filters, endpoint: "", status: "All", subaccount: "" }, NOW)).toEqual({
      since: "2026-09-13T12:00:00.000Z",
      until: "2026-09-20T12:00:00.000Z",
    });
  });

  it("Custom sends the chosen from and to as UTC instants", () => {
    const from = new Date(2026, 8, 1, 9, 0);
    const to = new Date(2026, 8, 2, 18, 30);

    const result = windowOf(
      {
        customFrom: minuteValue(from),
        customTo: minuteValue(to),
        endpoint: "",
        preset: "Custom",
        status: "All",
        subaccount: "",
      },
      NOW,
    );

    expect(result).toEqual({ since: from.toISOString(), until: to.toISOString() });
  });

  it("Custom with nothing chosen sends no since or until", () => {
    const result = windowOf(
      {
        customFrom: "",
        customTo: "",
        endpoint: "",
        preset: "Custom",
        status: "All",
        subaccount: "",
      },
      NOW,
    );

    expect(result).toEqual({ since: null, until: null });
  });
});

describe("logsQueryOf", () => {
  it("trims the subaccount and turns blanks into no filter", () => {
    const result = logsQueryOf(
      {
        customFrom: "",
        customTo: "",
        endpoint: "/api/v3/sms/send",
        preset: "Last 24 hours",
        status: "Successful",
        subaccount: "  user-1  ",
      },
      NOW,
    );

    expect(result).toEqual({
      endpoint: "/api/v3/sms/send",
      outcome: "ok",
      since: null,
      subaccount: "user-1",
      until: null,
    });
  });
});
