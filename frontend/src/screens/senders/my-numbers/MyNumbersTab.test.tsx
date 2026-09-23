import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { refusal } from "@/test/fakeFetch";
import type { FakeFetch } from "@/test/fakeFetch";
import { DEDICATED_OVERVIEW, DEDICATED_SENDER, PENDING_OVERVIEW } from "@/test/fixtures/senders";

import { openTab, renderSenders } from "../testing";

async function openMyNumbers(
  user: ReturnType<typeof userEvent.setup>,
  routes: Record<string, unknown> = {},
): Promise<FakeFetch> {
  const fetcher = renderSenders(routes);
  await openTab(user, "My Numbers");

  return fetcher;
}

describe("MyNumbersTab", () => {
  it("introduces the three kinds of number", async () => {
    await openMyNumbers(userEvent.setup());

    expect(
      screen.getByText("Purchase a dedicated phone number that is used by your business only."),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Connect your own mobile numbers with txtlocal for easy messaging."),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        "Use free shared numbers for cost effective SMS. Ideal for bulk messaging and promotions.",
      ),
    ).toBeInTheDocument();
  });

  it("sends Purchase to Buy A Number", async () => {
    await openMyNumbers(userEvent.setup());

    expect(screen.getByRole("link", { name: "+ Purchase" })).toHaveAttribute(
      "href",
      "/senders/buy",
    );
  });

  it("lists an own number with its nickname and last verified date", async () => {
    await openMyNumbers(userEvent.setup());
    const own = screen.getByRole("region", { name: "Own Numbers" });

    expect(within(own).getByText("Sam's Phone")).toBeInTheDocument();
    expect(within(own).getByText("+447400123123")).toBeInTheDocument();
    expect(within(own).getByText("19 Sept 2026")).toBeInTheDocument();
    expect(within(own).getByText("Ready to use")).toBeInTheDocument();
  });

  it("lists the free shared number of the pool", async () => {
    await openMyNumbers(userEvent.setup());
    const shared = screen.getByRole("region", { name: "Shared Numbers" });

    expect(within(shared).getByText("🌐")).toBeInTheDocument();
    expect(within(shared).getByText("Shared number")).toBeInTheDocument();
    expect(within(shared).getByText("MMS, SMS")).toBeInTheDocument();
    expect(within(shared).getByText("Ready to use")).toBeInTheDocument();
  });

  it("removes an own number", async () => {
    const user = userEvent.setup();
    const fetcher = await openMyNumbers(user);

    await user.click(screen.getByRole("button", { name: "Remove +447400123123" }));

    const removed = fetcher.calls.find((call) => call.method === "DELETE");
    expect(removed?.path).toBe("/api/app/senders/sender-own");
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("renders the server's refusal of a removal verbatim", async () => {
    const user = userEvent.setup();
    await openMyNumbers(user, {
      "DELETE /api/app/senders/sender-own": refusal(400, "Only own numbers can be removed"),
    });

    await user.click(screen.getByRole("button", { name: "Remove +447400123123" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Only own numbers can be removed");
  });

  it("offers Re-verify only while a number is pending", async () => {
    await openMyNumbers(userEvent.setup());

    expect(
      screen.queryByRole("button", { name: "Re-verify +447400123123" }),
    ).not.toBeInTheDocument();
  });

  it("reopens the add form filled in when re-verifying a pending number", async () => {
    const user = userEvent.setup();
    await openMyNumbers(user, { "GET /api/app/senders": PENDING_OVERVIEW });

    await user.click(screen.getByRole("button", { name: "Re-verify +447400123123" }));

    const dialog = screen.getByRole("dialog", { name: "Add your own number" });
    expect(within(dialog).getByLabelText("Nickname")).toHaveValue("New phone");
    expect(within(dialog).getByLabelText("Your Own Number")).toHaveValue("+447400123123");
  });

  it("lists a purchased dedicated number with its renewal date", async () => {
    await openMyNumbers(userEvent.setup(), { "GET /api/app/senders": DEDICATED_OVERVIEW });
    const dedicated = screen.getByRole("region", { name: "Dedicated Numbers" });

    expect(within(dedicated).getByText(DEDICATED_SENDER.value)).toBeInTheDocument();
    expect(within(dedicated).getByText("19 Oct 2026")).toBeInTheDocument();
    expect(within(dedicated).getByText("Ready to use")).toBeInTheDocument();
  });

  it("cancels a dedicated number", async () => {
    const user = userEvent.setup();
    const fetcher = await openMyNumbers(user, {
      [`DELETE /api/app/senders/${DEDICATED_SENDER.senderId}`]: new Response(null, {
        status: 204,
      }),
      "GET /api/app/senders": DEDICATED_OVERVIEW,
    });

    await user.click(screen.getByRole("button", { name: `Cancel ${DEDICATED_SENDER.value}` }));

    const cancelled = fetcher.calls.find((call) => call.method === "DELETE");
    expect(cancelled?.path).toBe(`/api/app/senders/${DEDICATED_SENDER.senderId}`);
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("hides Cancel number once a dedicated number is already cancelled", async () => {
    const cancelled = { ...DEDICATED_SENDER, cancelled: true };
    await openMyNumbers(userEvent.setup(), {
      "GET /api/app/senders": {
        ...DEDICATED_OVERVIEW,
        senders: { ...DEDICATED_OVERVIEW.senders, DEDICATED: [cancelled] },
      },
    });

    expect(
      screen.queryByRole("button", { name: `Cancel ${DEDICATED_SENDER.value}` }),
    ).not.toBeInTheDocument();
  });
});
