import { screen } from "@testing-library/react";
import type userEvent from "@testing-library/user-event";

import { fakeFetch } from "@/test/fakeFetch";
import type { FakeFetch } from "@/test/fakeFetch";
import { HOME } from "@/test/fixtures/identity";
import { SEND_RESULT } from "@/test/fixtures/messaging";
import { renderWithProviders } from "@/test/render";

import { HomeScreen } from "./HomeScreen";

export const PREVIEW_PLACEHOLDER = "Type a message to see preview";

export function renderHome(routes: Record<string, unknown> = {}): FakeFetch {
  const fetcher = fakeFetch({
    "GET /api/app/home": HOME,
    "POST /api/app/messages/send": SEND_RESULT,
    ...routes,
  });
  renderWithProviders(<HomeScreen />, { fetcher });

  return fetcher;
}

export async function fillTestSend(user: ReturnType<typeof userEvent.setup>): Promise<void> {
  await screen.findByText(PREVIEW_PLACEHOLDER);
  await user.type(screen.getByLabelText("Recipient"), "+447700900105, +447700900100");
  await user.type(screen.getByLabelText("Message content"), "Hello");
  await user.click(screen.getByRole("button", { name: "SEND TEST MESSAGE" }));
}
