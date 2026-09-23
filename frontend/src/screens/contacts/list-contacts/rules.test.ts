import { describe, expect, it } from "vitest";

import type { Contact } from "@/api/generated/dashboard";

import { isCleanUpAction, sortValueOf, toggledAll, toggledOne } from "./rules";

const SAM: Contact = {
  accountId: "account-1",
  cf1: "",
  cf2: "",
  cf3: "",
  cf4: "",
  email: "",
  firstName: "Sam",
  lastName: "Ray",
  listId: "list-1",
  mobile: "+447400123123",
  updatedAt: "2026-09-19T12:00:00Z",
};

describe("sortValueOf", () => {
  it.each([
    { expected: "Sam", key: "firstName", label: "reads the sorted column of a contact" },
    { expected: "", key: "nothing", label: "reads nothing for an unknown column" },
  ] as const)("$label", ({ expected, key }) => {
    expect(sortValueOf(SAM, key)).toBe(expected);
  });
});

describe("selection", () => {
  it("adds a mobile that is not selected", () => {
    expect([...toggledOne(new Set<string>(), "+447400123123")]).toEqual(["+447400123123"]);
  });

  it("removes a mobile that is selected", () => {
    expect([...toggledOne(new Set(["+447400123123"]), "+447400123123")]).toEqual([]);
  });

  it("selects every row when some are unselected", () => {
    expect([...toggledAll(["a", "b"], new Set(["a"]))]).toEqual(["a", "b"]);
  });

  it("clears the selection when every row is selected", () => {
    expect([...toggledAll(["a", "b"], new Set(["a", "b"]))]).toEqual([]);
  });
});

describe("labels", () => {
  it.each([
    { label: "accepts INVALID", value: "INVALID", wanted: true },
    { label: "accepts OPTED_OUT", value: "OPTED_OUT", wanted: true },
    { label: "rejects anything else", value: "DELETE", wanted: false },
  ] as const)("$label", ({ value, wanted }) => {
    expect(isCleanUpAction(value)).toBe(wanted);
  });
});
