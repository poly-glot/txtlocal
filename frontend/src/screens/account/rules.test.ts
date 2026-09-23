import { describe, expect, it } from "vitest";

import { countryOptions } from "./rules";

describe("countryOptions", () => {
  it("names each country after its code", () => {
    expect(countryOptions(["GB"])).toEqual([{ label: "GB — United Kingdom", value: "GB" }]);
  });
});
