import { describe, expect, it } from "vitest";

import { noticeOf, refusalNotice, undismissedRefusalNotice } from "./notice";

const OK = { data: null, status: "OK" } as const;
const REFUSED = { message: "Nope", status: "ERROR" } as const;

describe("noticeOf", () => {
  it.each([
    { expected: { message: "Saved.", tone: "success" }, label: "success copy", result: OK },
    { expected: { message: "Nope", tone: "error" }, label: "server refusal", result: REFUSED },
  ] as const)("$label", ({ expected, result }) => {
    expect(noticeOf(result, "Saved.")).toEqual(expected);
  });
});

describe("refusalNotice", () => {
  it.each([
    { expected: undefined, label: "nothing on success", result: OK },
    { expected: { message: "Nope", tone: "error" }, label: "the refusal", result: REFUSED },
  ] as const)("$label", ({ expected, result }) => {
    expect(refusalNotice(result)).toEqual(expected);
  });
});

describe("undismissedRefusalNotice", () => {
  it.each([
    {
      dismissedAt: 0,
      expected: { message: "Nope", tone: "error" },
      label: "a fresh refusal",
      result: REFUSED,
    },
    { dismissedAt: 1, expected: undefined, label: "a dismissed refusal", result: REFUSED },
    { dismissedAt: 0, expected: undefined, label: "a success", result: OK },
  ] as const)("$label", ({ dismissedAt, expected, result }) => {
    expect(undismissedRefusalNotice(result, dismissedAt, 1)).toEqual(expected);
  });
});
