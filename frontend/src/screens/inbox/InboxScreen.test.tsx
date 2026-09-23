import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { JANE_CONVERSATION, JANE_PEER } from "@/test/fixtures/inbox";
import { field, refusal } from "@/test/fakeFetch";

import { renderInbox } from "./testing";

const REPLY_PATH = `/api/app/conversations/${encodeURIComponent(JANE_PEER)}/messages`;
const REPLY_ROUTE = `POST ${REPLY_PATH}`;
const REPLY_SENT = { campaignId: "campaign-2", costMicro: 3200, recipients: 1, refused: [] };

describe("InboxScreen", () => {
  it("shows the empty state when no conversation is selected", async () => {
    renderInbox();

    expect(await screen.findByText("Select a conversation to start sending")).toBeInTheDocument();
  });

  it("shows an unread badge on a conversation with unread messages", async () => {
    renderInbox();
    const conversations = await screen.findByRole("region", { name: "Inbox" });

    expect(
      await within(conversations).findByText(String(JANE_CONVERSATION.unread)),
    ).toBeInTheDocument();
  });

  it("opens a conversation and shows its messages", async () => {
    const user = userEvent.setup();
    renderInbox();

    await user.click(await screen.findByText("Jane Austen"));

    const conversation = await screen.findByRole("region", { name: "Conversation" });
    expect(await within(conversation).findByText("Yes, see you at 10.")).toBeInTheDocument();
    expect(
      within(conversation).getByText("Hey, are we still on for tomorrow?"),
    ).toBeInTheDocument();
  });

  it("sends a reply from the open conversation", async () => {
    const user = userEvent.setup();
    const fetcher = renderInbox({ [REPLY_ROUTE]: REPLY_SENT });

    await user.click(await screen.findByText("Jane Austen"));
    await user.type(await screen.findByLabelText("Message"), "On my way!");
    await user.click(screen.getByRole("button", { name: "SEND" }));

    await waitFor(() => {
      expect(screen.getByLabelText("Message")).toHaveValue("");
    });
    const call = fetcher.calls.find((one) => one.method === "POST" && one.path === REPLY_PATH);
    expect(field(call, "body")).toBe("On my way!");
  });

  it("replies from the sender the contact last wrote to", async () => {
    const user = userEvent.setup();
    const fetcher = renderInbox({ [REPLY_ROUTE]: REPLY_SENT });

    await user.click(await screen.findByText("Jane Austen"));
    await user.type(await screen.findByLabelText("Message"), "On my way!");
    await user.click(screen.getByRole("button", { name: "SEND" }));

    await waitFor(() => {
      expect(screen.getByLabelText("Message")).toHaveValue("");
    });
    const call = fetcher.calls.find((one) => one.method === "POST" && one.path === REPLY_PATH);
    expect(field(call, "senderId")).toBe("sender-own");
  });

  it("replies through Smart Senders when they are chosen in From", async () => {
    const user = userEvent.setup();
    const fetcher = renderInbox({ [REPLY_ROUTE]: REPLY_SENT });

    await user.click(await screen.findByText("Jane Austen"));
    await user.selectOptions(await screen.findByLabelText("From"), "Smart Senders");
    await user.type(screen.getByLabelText("Message"), "On my way!");
    await user.click(screen.getByRole("button", { name: "SEND" }));

    await waitFor(() => {
      expect(screen.getByLabelText("Message")).toHaveValue("");
    });
    const call = fetcher.calls.find((one) => one.method === "POST" && one.path === REPLY_PATH);
    expect(field(call, "senderId")).toBeNull();
  });

  it("renders the server's refusal of a reply verbatim", async () => {
    const user = userEvent.setup();
    renderInbox({ [REPLY_ROUTE]: refusal(400, "This contact has opted out") });

    await user.click(await screen.findByText("Jane Austen"));
    await user.type(await screen.findByLabelText("Message"), "Hello");
    await user.click(screen.getByRole("button", { name: "SEND" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("This contact has opted out");
  });

  it("marks every conversation read from the overflow menu", async () => {
    const user = userEvent.setup();
    const fetcher = renderInbox({ "POST /api/app/conversations/read-all": {} });

    await user.click(await screen.findByRole("button", { name: "More actions" }));
    await user.click(screen.getByRole("button", { name: "Mark all as read" }));

    await waitFor(() => {
      expect(
        fetcher.calls.some(
          (call) => call.method === "POST" && call.path === "/api/app/conversations/read-all",
        ),
      ).toBe(true);
    });
  });

  it("asks the server to close an open conversation", async () => {
    const user = userEvent.setup();
    const fetcher = renderInbox({
      [`POST /api/app/conversations/${encodeURIComponent(JANE_PEER)}/close`]: {
        ...JANE_CONVERSATION,
        status: "CLOSED",
      },
    });

    await user.click(await screen.findByText("Jane Austen"));
    await user.click(await screen.findByRole("button", { name: "Close conversation" }));

    await waitFor(() => {
      expect(
        fetcher.calls.some(
          (call) =>
            call.method === "POST" &&
            call.path === `/api/app/conversations/${encodeURIComponent(JANE_PEER)}/close`,
        ),
      ).toBe(true);
    });
  });
});
