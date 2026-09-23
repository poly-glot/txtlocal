import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { field, refusal } from "@/test/fakeFetch";
import { CONTACT_HIT } from "@/test/fixtures/messaging";

import { renderQuickMms, renderQuickSms } from "./testing";

const HELPER =
  "The best sender has been auto-selected from Smart Senders. Reset the Smart Sender for each country. Or select an approved number or sender above.";

async function compose(user: ReturnType<typeof userEvent.setup>): Promise<void> {
  await user.type(await screen.findByLabelText("To"), "+447400123105{Enter}");
  await user.type(screen.getByLabelText("Message"), "Hello");
}

describe("QuickSendScreen", () => {
  it("explains how the sender was chosen", async () => {
    renderQuickSms();

    expect(await screen.findByLabelText("From")).toHaveAccessibleDescription(HELPER);
  });

  it("names every part of the compose form", async () => {
    renderQuickSms();

    expect(await screen.findByLabelText("To")).toHaveAttribute(
      "placeholder",
      "Search Contact/List or enter Mobile number",
    );
    expect(screen.getByLabelText("Message")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Placeholder" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Template" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Emoji" })).toBeInTheDocument();
    expect(screen.getByText("NEW")).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: "Now" })).toBeChecked();
  });

  it("groups the senders and offers a way to add the empty ones", async () => {
    renderQuickSms();

    expect(await screen.findByRole("group", { name: "Smart Senders" })).toBeInTheDocument();
    expect(screen.getByRole("group", { name: "Own Numbers" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Purchase Dedicated Numbers" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Add Alpha Tags" })).toBeInTheDocument();
  });

  it("mirrors the message in the sender's preview", async () => {
    const user = userEvent.setup();
    renderQuickSms();
    const preview = await screen.findByRole("region", { name: "Message preview" });

    expect(within(preview).getByText("Type a message to see preview")).toBeInTheDocument();
    await user.type(screen.getByLabelText("Message"), "Hello");

    expect(within(preview).getByText("Smart Senders")).toBeInTheDocument();
    expect(within(preview).getByText("Hello")).toBeInTheDocument();
  });

  it("offers the account's own number as a sender", async () => {
    renderQuickSms();

    expect(
      await screen.findByRole("option", { name: "+447400123123 (Own Number)" }),
    ).toBeInTheDocument();
  });

  it("counts characters and parts as the message grows", async () => {
    const user = userEvent.setup();
    renderQuickSms();

    await user.type(await screen.findByLabelText("Message"), "Hello");

    expect(screen.getByText("Approx. 5 characters/1 SMS per recipient.")).toBeInTheDocument();
  });

  it("keeps the preview button disabled until a recipient and a message exist", async () => {
    const user = userEvent.setup();
    renderQuickSms();
    const button = await screen.findByRole("button", { name: "PREVIEW AND CONFIRM" });

    expect(button).toBeDisabled();
    await compose(user);

    expect(button).toBeEnabled();
  });

  it("accepts a typed number when contact search is unavailable", async () => {
    const user = userEvent.setup();
    renderQuickSms();

    await user.type(await screen.findByLabelText("To"), "07411972333{Enter}");

    expect(screen.getByRole("button", { name: "Remove 07411972333" })).toBeInTheDocument();
  });

  it("opens with the list the contacts screen chose", async () => {
    renderQuickSms({}, "/sms/quick?listId=list-example");

    expect(
      await screen.findByRole("button", { name: "Remove Example List (2)" }),
    ).toBeInTheDocument();
  });

  it("offers a matching list but never the opt-out list", async () => {
    const user = userEvent.setup();
    renderQuickSms();

    await user.type(await screen.findByLabelText("To"), "list");

    expect(screen.getByRole("button", { name: "Example List (2)" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Opt-Out List/ })).not.toBeInTheDocument();
  });

  it("sends a list on its own as listIds with no numbers", async () => {
    const user = userEvent.setup();
    const fetcher = renderQuickSms({}, "/sms/quick?listId=list-example");
    await screen.findByRole("button", { name: "Remove Example List (2)" });
    await user.type(screen.getByLabelText("Message"), "Hello");

    await user.click(screen.getByRole("button", { name: "PREVIEW AND CONFIRM" }));
    await user.click(await screen.findByRole("button", { name: "SEND" }));

    await screen.findByText("Your message is on its way.");
    const send = fetcher.calls.find((call) => call.path === "/api/app/messages/send");
    expect(send?.body).toEqual({
      body: "Hello",
      kind: "SMS",
      listIds: ["list-example"],
      mediaKey: null,
      messageType: "PROMOTIONAL",
      sendAt: null,
      senderId: null,
      shortenUrls: false,
      subject: "",
      to: [],
    });
  });

  it("renders the server's refusal of an unknown list verbatim", async () => {
    const user = userEvent.setup();
    renderQuickSms(
      { "POST /api/app/messages/quote": refusal(404, "List not found") },
      "/sms/quick?listId=list-example",
    );
    await screen.findByRole("button", { name: "Remove Example List (2)" });
    await user.type(screen.getByLabelText("Message"), "Hello");

    await user.click(screen.getByRole("button", { name: "PREVIEW AND CONFIRM" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("List not found");
  });

  it("adds a contact from the typeahead with its name and number", async () => {
    const user = userEvent.setup();
    renderQuickSms({ "GET /api/app/contacts/search?limit=8&q=Sam": [CONTACT_HIT] });

    await user.type(await screen.findByLabelText("To"), "Sam");
    await user.click(await screen.findByRole("button", { name: "Sam Patel +447400123105" }));

    expect(
      screen.getByRole("button", { name: "Remove Sam Patel +447400123105" }),
    ).toBeInTheDocument();
  });

  it("shows the recipients, delivery and cost before sending", async () => {
    const user = userEvent.setup();
    renderQuickSms();
    await compose(user);

    await user.click(screen.getByRole("button", { name: "PREVIEW AND CONFIRM" }));
    const dialog = await screen.findByRole("dialog", { name: "Confirm SMS Send" });

    expect(within(dialog).getByText("Recipients:")).toBeInTheDocument();
    expect(within(dialog).getByText("2")).toBeInTheDocument();
    expect(within(dialog).getByText("Deliver:")).toBeInTheDocument();
    expect(within(dialog).getByText("Immediately")).toBeInTheDocument();
    expect(within(dialog).getByText("Cost deducted:")).toBeInTheDocument();
    expect(within(dialog).getByRole("button", { name: "CLOSE" })).toBeInTheDocument();
    expect(within(dialog).getByText("£0.0854")).toBeInTheDocument();
  });

  it("sends the composed message and confirms it is on its way", async () => {
    const user = userEvent.setup();
    const fetcher = renderQuickSms();
    await compose(user);

    await user.click(screen.getByRole("button", { name: "PREVIEW AND CONFIRM" }));
    await user.click(await screen.findByRole("button", { name: "SEND" }));

    expect(await screen.findByText("Your message is on its way.")).toBeInTheDocument();
    const send = fetcher.calls.find((call) => call.path === "/api/app/messages/send");
    expect(send?.body).toEqual({
      body: "Hello",
      kind: "SMS",
      listIds: [],
      mediaKey: null,
      messageType: "PROMOTIONAL",
      sendAt: null,
      senderId: null,
      shortenUrls: false,
      subject: "",
      to: ["+447400123105"],
    });
  });

  it("asks for tracked links when the shorten toggle is on", async () => {
    const user = userEvent.setup();
    const fetcher = renderQuickSms();
    await compose(user);

    await user.click(screen.getByLabelText("Shorten my URL"));
    await user.click(screen.getByRole("button", { name: "PREVIEW AND CONFIRM" }));
    await screen.findByRole("dialog", { name: "Confirm SMS Send" });

    const quote = fetcher.calls.findLast((call) => call.path === "/api/app/messages/quote");
    expect(field(quote, "shortenUrls")).toBe(true);
  });

  it("renders the server's refusal verbatim", async () => {
    const user = userEvent.setup();
    renderQuickSms({
      "POST /api/app/messages/quote": refusal(400, "Sending to FR is not enabled for this account"),
    });
    await compose(user);

    await user.click(screen.getByRole("button", { name: "PREVIEW AND CONFIRM" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Sending to FR is not enabled for this account",
    );
  });

  it("offers a send time later than now", async () => {
    const user = userEvent.setup();
    renderQuickSms();

    await user.click(await screen.findByRole("radio", { name: "Later" }));

    expect(screen.getByLabelText("Send at")).toBeInTheDocument();
  });
});

describe("QuickSendPage on MMS", () => {
  it("warns that MMS is not supported in every country", async () => {
    renderQuickMms();

    expect(await screen.findByText("MMS is not supported in all countries.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "See supported countries here" })).toBeInTheDocument();
  });
});
