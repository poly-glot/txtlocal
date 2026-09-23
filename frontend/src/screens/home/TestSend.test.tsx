import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { refusal } from "@/test/fakeFetch";
import { SEND_RESULT } from "@/test/fixtures/messaging";

import { PREVIEW_PLACEHOLDER, fillTestSend, renderHome } from "./testing";

describe("TestSend", () => {
  it("shows the temporary sender and how to enter recipients", async () => {
    renderHome();

    expect(await screen.findByLabelText("Sender ID")).toHaveValue("txtlocal Sender ID");
    expect(screen.getByLabelText("Sender ID")).toHaveAccessibleDescription(
      "This is your temporary Sender ID for testing. You can set up your own whenever you're ready.",
    );
    expect(screen.getByLabelText("Recipient")).toHaveAccessibleDescription(
      "Start typing a number. You can enter multiple numbers separated by a comma.",
    );
  });

  it("counts characters and parts as the message grows", async () => {
    const user = userEvent.setup();
    renderHome();
    await screen.findByText(PREVIEW_PLACEHOLDER);

    expect(screen.getByLabelText("Message content")).toHaveAccessibleDescription(
      "Approx. 0 characters/1 SMS per recipient.",
    );
    await user.type(screen.getByLabelText("Message content"), "Hello");

    expect(screen.getByLabelText("Message content")).toHaveAccessibleDescription(
      "Approx. 5 characters/1 SMS per recipient.",
    );
    expect(screen.getByText("5 / 1224")).toBeInTheDocument();
    expect(screen.getByText("credit")).toHaveTextContent("£2.00 credit");
  });

  it("keeps the send button disabled until a recipient and text exist", async () => {
    const user = userEvent.setup();
    renderHome();
    await screen.findByText(PREVIEW_PLACEHOLDER);
    const button = screen.getByRole("button", { name: "SEND TEST MESSAGE" });

    expect(button).toBeDisabled();
    await user.type(screen.getByLabelText("Recipient"), "+447700900105");
    expect(button).toBeDisabled();
    await user.type(screen.getByLabelText("Message content"), "Hello");

    expect(button).toBeEnabled();
  });

  it("posts the body and recipients without a sender and confirms", async () => {
    const user = userEvent.setup();
    const fetcher = renderHome();

    await fillTestSend(user);

    expect(await screen.findByText("Test message sent.")).toBeInTheDocument();
    const send = fetcher.calls.find((call) => call.path === "/api/app/messages/send");
    expect(send?.body).toEqual({
      body: "Hello",
      kind: "SMS",
      messageType: "PROMOTIONAL",
      shortenUrls: false,
      subject: "",
      to: ["+447700900105", "+447700900100"],
    });
    expect(screen.getByLabelText("Message content")).toHaveValue("");
  });

  it("renders the server's refusal verbatim", async () => {
    const user = userEvent.setup();
    renderHome({
      "POST /api/app/messages/send": refusal(402, "Your balance is £0.00; this send costs £0.04"),
    });

    await fillTestSend(user);

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Your balance is £0.00; this send costs £0.04",
    );
  });

  it("renders a per-recipient refusal's sentence, not its code", async () => {
    const user = userEvent.setup();
    renderHome({
      "POST /api/app/messages/send": {
        ...SEND_RESULT,
        refused: [
          { message: "This contact has opted out", reason: "OPTED_OUT", to: "+447700900105" },
        ],
      },
    });

    await fillTestSend(user);

    expect(await screen.findByRole("alert")).toHaveTextContent("This contact has opted out");
  });
});
