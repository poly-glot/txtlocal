import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Money } from "./Money";

describe("Money", () => {
  it.each([
    {
      label: "a package price shows whole pounds",
      micro: 1_500_000_000,
      places: 0,
      text: "£1,500",
    },
    { label: "whole pounds keep two places", micro: 2_000_000, places: 2, text: "£2.00" },
    { label: "a unit price shows four places", micro: 42_700, places: 4, text: "£0.0427" },
    { label: "a unit price at two places rounds", micro: 42_700, places: 2, text: "£0.04" },
    { label: "thousands are grouped", micro: 1_170_000_000, places: 2, text: "£1,170.00" },
  ] as const)("$label", ({ micro, places, text }) => {
    render(<Money micro={micro} places={places} />);

    expect(screen.getByText(text)).toBeInTheDocument();
  });

  it("defaults to two places", () => {
    render(<Money micro={42_700} />);

    expect(screen.getByText("£0.04")).toBeInTheDocument();
  });
});
