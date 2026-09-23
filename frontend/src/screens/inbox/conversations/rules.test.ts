import { describe, expect, it } from "vitest";

import {
  initialsOf,
  looksLikeNumber,
  relativeTimeOf,
  statusFilterOf,
  statusQueryValue,
} from "./rules";

describe("initialsOf", () => {
  it.each([
    { label: "a first and last name take one letter each", name: "Jane Austen", value: "JA" },
    { label: "a single name takes its first letter", name: "Cher", value: "C" },
    { label: "three names keep only the first two", name: "Mary Jane Watson", value: "MJ" },
    { label: "an unresolved number has no letters", name: "+447400123123", value: "#" },
    { label: "an empty name has no letters", name: "", value: "#" },
  ] as const)("$label", ({ name, value }) => {
    expect(initialsOf(name)).toBe(value);
  });
});

describe("looksLikeNumber", () => {
  it.each([
    { label: "a full E.164 number", q: "+447400123123", value: true },
    { label: "a local number with no country code", q: "07400123123", value: true },
    { label: "spaces inside a number are stripped", q: "+44 7400 123123", value: true },
    { label: "a name is not a number", q: "John", value: false },
    { label: "too few digits is not a number", q: "12345", value: false },
    { label: "too many digits is not a number", q: "1234567890123456", value: false },
    { label: "an empty string is not a number", q: "", value: false },
  ] as const)("$label", ({ q, value }) => {
    expect(looksLikeNumber(q)).toBe(value);
  });
});

describe("statusFilterOf", () => {
  it.each([
    { input: "OPEN", label: "OPEN stays OPEN", output: "OPEN" },
    { input: "CLOSED", label: "CLOSED stays CLOSED", output: "CLOSED" },
    { input: "ALL", label: "ALL stays ALL", output: "ALL" },
    { input: "bogus", label: "an unknown value defaults to OPEN", output: "OPEN" },
  ] as const)("$label", ({ input, output }) => {
    expect(statusFilterOf(input)).toBe(output);
  });
});

describe("statusQueryValue", () => {
  it.each([
    { filter: "OPEN", label: "OPEN is sent as OPEN", value: "OPEN" },
    { filter: "CLOSED", label: "CLOSED is sent as CLOSED", value: "CLOSED" },
    { filter: "ALL", label: "ALL is sent as no filter", value: null },
  ] as const)("$label", ({ filter, value }) => {
    expect(statusQueryValue(filter)).toBe(value);
  });
});

describe("relativeTimeOf", () => {
  const now = new Date("2026-09-19T12:00:00Z");

  it.each([
    { at: "2026-09-19T11:59:31Z", label: "under a minute ago is now", value: "now" },
    { at: "2026-09-19T11:50:00Z", label: "ten minutes ago", value: "10m" },
    { at: "2026-09-19T10:00:00Z", label: "two hours ago", value: "2h" },
    { at: "2026-09-17T12:00:00Z", label: "two days ago", value: "2d" },
  ] as const)("$label", ({ at, value }) => {
    expect(relativeTimeOf(at, now, "UTC")).toBe(value);
  });

  it("falls back to a full date after a week", () => {
    expect(relativeTimeOf("2026-09-01T12:00:00Z", now, "UTC")).toBe("01/09/2026, 12:00");
  });
});
