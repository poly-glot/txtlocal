import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Section } from "./Section";

describe("Section", () => {
  it("names its region after its title", () => {
    render(<Section title="Contact">fields</Section>);

    expect(screen.getByRole("region", { name: "Contact" })).toHaveTextContent("fields");
  });
});
