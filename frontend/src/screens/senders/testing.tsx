import { screen, waitFor } from "@testing-library/react";
import type userEvent from "@testing-library/user-event";
import { expect } from "vitest";

import { fakeFetch } from "@/test/fakeFetch";
import type { FakeFetch } from "@/test/fakeFetch";
import { ALPHA_SENDER, OVERVIEW, OWN_SENDER, PENDING_SENDER } from "@/test/fixtures/senders";
import { renderWithProviders } from "@/test/render";

import { ManageSendersScreen } from "./ManageSendersScreen";

type User = ReturnType<typeof userEvent.setup>;

export function renderSenders(routes: Record<string, unknown> = {}): FakeFetch {
  const fetcher = fakeFetch({
    [`DELETE /api/app/senders/${OWN_SENDER.senderId}`]: new Response(null, { status: 204 }),
    "GET /api/app/senders": OVERVIEW,
    "POST /api/app/senders/alpha": ALPHA_SENDER,
    "POST /api/app/senders/own": PENDING_SENDER,
    [`POST /api/app/senders/own/${PENDING_SENDER.senderId}/verify`]: OWN_SENDER,
    "PUT /api/app/senders/smart/GB": { channel: "SMS", country: "GB", senderId: "sender-own" },
    ...routes,
  });
  renderWithProviders(<ManageSendersScreen />, { fetcher });

  return fetcher;
}

export async function openTab(user: User, name: string): Promise<void> {
  await user.click(await screen.findByRole("tab", { name }));
}

export async function addOwnNumber(user: User, code: string): Promise<void> {
  await openTab(user, "My Numbers");
  await user.click(screen.getByRole("button", { name: "+ Add" }));
  await user.type(screen.getByLabelText("Nickname"), "New phone");
  await user.type(screen.getByLabelText("Your Own Number"), "07400123123");
  await user.click(screen.getByRole("button", { name: "Send Code" }));

  const codeField = screen.getByLabelText("Verification Code");
  await waitFor(() => {
    expect(codeField).toBeEnabled();
  });
  await user.type(codeField, code);
  await user.click(screen.getByRole("button", { name: "Add Number" }));
}
