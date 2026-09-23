import { describe, expect, it } from "vitest";

import { toProfileUpdate } from "./rules";

describe("toProfileUpdate", () => {
  it("omits a blank phone", () => {
    expect(toProfileUpdate({ firstName: "Sam", lastName: "Patel", phone: "" })).toEqual({
      firstName: "Sam",
      lastName: "Patel",
    });
  });

  it("keeps a phone that was entered", () => {
    expect(toProfileUpdate({ firstName: "Sam", lastName: "Patel", phone: "07700900105" })).toEqual({
      firstName: "Sam",
      lastName: "Patel",
      phone: "07700900105",
    });
  });
});
