import { describe, expect, it } from "vitest";

import { OVERVIEW, OWN_SENDER } from "@/test/fixtures/senders";

import { countryLabel, enabledCountriesOf, senderOptionsFor } from "./rules";

describe("countryLabel", () => {
  it.each([
    { country: "GB", label: "names the United Kingdom", want: "🇬🇧 United Kingdom +44" },
    { country: "US", label: "names the United States", want: "🇺🇸 United States +1" },
    { country: "CA", label: "names Canada", want: "🇨🇦 Canada +1" },
  ] as const)("$label", ({ country, want }) => {
    expect(countryLabel(country)).toBe(want);
  });
});

describe("enabledCountriesOf", () => {
  it("lists one country per shared sender", () => {
    expect(enabledCountriesOf(OVERVIEW)).toEqual(["GB"]);
  });

  it("lists nothing when no shared sender exists", () => {
    expect(enabledCountriesOf({ senders: {}, smart: {} })).toEqual([]);
  });
});

describe("senderOptionsFor", () => {
  it("offers the ready senders of the country with the shared pool last", () => {
    expect(senderOptionsFor(OVERVIEW, "GB")).toEqual([
      { label: "+447400123123 (Own Number)", value: "sender-own" },
      { label: "Shared Numbers", value: "sender-shared" },
    ]);
  });

  it("leaves out a sender that is not ready", () => {
    const view = {
      ...OVERVIEW,
      senders: { OWN: [{ ...OWN_SENDER, status: "PENDING_VERIFICATION" as const }] },
    };

    expect(senderOptionsFor(view, "GB")).toEqual([]);
  });

  it("leaves out a sender of another country", () => {
    expect(senderOptionsFor(OVERVIEW, "US")).toEqual([]);
  });
});
