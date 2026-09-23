import { describe, expect, it } from "vitest";

import { mmsCounterText } from "./rules";

describe("mmsCounterText", () => {
  it("counts characters against the 1500 character ceiling whatever the length", () => {
    expect(mmsCounterText("Hello")).toBe("Approx. 5 characters/1500 characters allowed");
  });

  it("counts an extended GSM character as two characters", () => {
    expect(mmsCounterText("€")).toBe("Approx. 2 characters/1500 characters allowed");
  });
});
