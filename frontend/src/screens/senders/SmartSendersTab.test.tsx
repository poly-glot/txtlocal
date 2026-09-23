import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { field, refusal } from "@/test/fakeFetch";

import { renderSenders } from "./testing";

const SMART_COPY =
  "We've automatically set the safest and best senders for each country — that's why they're called Smart Senders. You can update them if needed. We'll only show senders that are compliant for each location. You can use Smart Senders in our SMS products.";

describe("SmartSendersTab", () => {
  it("explains what a smart sender is and links to Global Sending", async () => {
    renderSenders();

    expect(await screen.findByText(SMART_COPY)).toBeInTheDocument();
    expect(screen.getByText("Learn about Smart Senders")).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Enable more countries via Global Sending" }),
    ).toHaveAttribute("href", "/account");
  });

  it("shows one row per enabled country defaulting to the shared pool", async () => {
    renderSenders();

    expect(await screen.findByText("🇬🇧 United Kingdom +44")).toBeInTheDocument();
    expect(screen.getByLabelText("Smart Sender")).toHaveValue("sender-shared");
    expect(screen.getByRole("option", { name: "Shared Numbers" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "+447400123123 (Own Number)" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Use for" })).toBeInTheDocument();
  });

  it("saves the chosen sender for that country", async () => {
    const user = userEvent.setup();
    const fetcher = renderSenders();

    await user.selectOptions(await screen.findByLabelText("Smart Sender"), "sender-own");

    const put = fetcher.calls.find((call) => call.method === "PUT");
    expect(put?.path).toBe("/api/app/senders/smart/GB");
    expect(field(put, "senderId")).toBe("sender-own");
  });

  it("renders the server's refusal verbatim", async () => {
    const user = userEvent.setup();
    renderSenders({
      "PUT /api/app/senders/smart/GB": refusal(400, "Shared Number is not ready to send to GB"),
    });

    await user.selectOptions(await screen.findByLabelText("Smart Sender"), "sender-own");

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Shared Number is not ready to send to GB",
    );
  });
});
