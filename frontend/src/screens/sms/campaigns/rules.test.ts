import { describe, expect, it } from "vitest";

import { DRAFT, SCHEDULED } from "@/test/fixtures/campaigns";

import { whenOf } from "./rules";

describe("whenOf", () => {
  it("shows the scheduled moment once a campaign has one", () => {
    expect(whenOf(SCHEDULED)).toBe("2027-07-31T22:59:00Z");
  });

  it("falls back to when the campaign was created", () => {
    expect(whenOf(DRAFT)).toBe("2026-09-19T10:00:00Z");
  });
});
