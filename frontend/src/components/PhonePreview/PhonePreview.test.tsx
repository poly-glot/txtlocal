import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { PhonePreview } from "./PhonePreview";

const preview = () => screen.getByRole("region", { name: "Message preview" });

describe("PhonePreview", () => {
  it("invites a message while the body is empty", () => {
    render(<PhonePreview body="" title="Sender ID" />);

    expect(within(preview()).getByText("Type a message to see preview")).toBeInTheDocument();
  });

  it("shows the body as a message bubble", () => {
    render(<PhonePreview body="Hello there" title="Sender ID" />);

    expect(within(preview()).getByText("Hello there")).toBeInTheDocument();
    expect(within(preview()).queryByText("Type a message to see preview")).not.toBeInTheDocument();
  });

  it("adds the footer as a second bubble", () => {
    render(<PhonePreview body="Hello" footer="Reply STOP to opt out" title="Reply num" />);

    expect(within(preview()).getByText("Reply STOP to opt out")).toBeInTheDocument();
  });

  it("captions the handset when asked", () => {
    render(<PhonePreview body="" caption="Preview on a handset" title="Sender ID" />);

    expect(screen.getByText("Preview on a handset")).toBeInTheDocument();
  });
});
