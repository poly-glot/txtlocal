import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { StatusPanel } from "./StatusPanel";

describe("StatusPanel", () => {
  it("keeps the panel title while it waits", () => {
    render(<StatusPanel title="Lists" />);

    expect(screen.getByRole("region", { name: "Lists" })).toHaveTextContent("Loading…");
  });

  it("shows the error inside the titled panel", () => {
    render(<StatusPanel error="Something went wrong on our side" title="Lists" />);

    expect(screen.getByRole("region", { name: "Lists" })).toHaveTextContent(
      "Something went wrong on our side",
    );
  });
});
