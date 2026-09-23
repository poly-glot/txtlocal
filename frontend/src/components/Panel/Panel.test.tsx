import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Panel } from "./Panel";

describe("Panel", () => {
  it("names its region after its title", () => {
    render(<Panel title="Lists">body</Panel>);

    expect(screen.getByRole("region", { name: "Lists" })).toBeInTheDocument();
  });

  it("stays an unnamed section without a title", () => {
    render(<Panel>body</Panel>);

    expect(screen.queryByRole("region")).not.toBeInTheDocument();
  });
});
