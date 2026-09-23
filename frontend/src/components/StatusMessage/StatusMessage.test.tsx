import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { StatusMessage } from "./StatusMessage";

describe("StatusMessage", () => {
  it("says it is loading until an error arrives", () => {
    render(<StatusMessage />);

    expect(screen.getByText("Loading…")).toBeInTheDocument();
  });

  it("shows the error as an alert", () => {
    render(<StatusMessage error="Something went wrong on our side" />);

    expect(screen.getByRole("alert")).toHaveTextContent("Something went wrong on our side");
  });
});
