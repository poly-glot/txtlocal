import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { stubLocation } from "@/test/signIn";

import { renderCardsScreen } from "./testing";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("CardsScreen", () => {
  it("lists saved cards with the default badge", async () => {
    renderCardsScreen();

    expect(await screen.findByText("Default")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Make default: visa •••• 0002" }),
    ).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: /Remove card:/ })).toHaveLength(2);
  });

  it("shows the empty state when no card is saved", async () => {
    renderCardsScreen({ "GET /api/app/billing/cards": [] });

    expect(await screen.findByText("No card")).toBeInTheDocument();
  });

  it("titles the panel Manage Credit Cards", async () => {
    renderCardsScreen();

    expect(await screen.findByRole("heading", { name: "Manage Credit Cards" })).toBeInTheDocument();
  });

  it("sends the browser to checkout when adding a card", async () => {
    const user = userEvent.setup();
    stubLocation();
    const CHECKOUT_URL = "https://pay.test/setup/abc";
    renderCardsScreen({ "POST /api/app/billing/cards": { checkoutUrl: CHECKOUT_URL } });
    await screen.findByText("Default");

    await user.click(screen.getByRole("button", { name: "Add new card" }));

    await waitFor(() => {
      expect(window.location.href).toBe(CHECKOUT_URL);
    });
  });

  it("makes a non-default card the default", async () => {
    const user = userEvent.setup();
    const fetcher = renderCardsScreen({ "PUT /api/app/billing/cards/pm_demo_0002/default": {} });
    await screen.findByText("Default");

    await user.click(screen.getByRole("button", { name: "Make default: visa •••• 0002" }));

    await waitFor(() => {
      expect(
        fetcher.calls.some((call) => call.method === "PUT" && call.path.includes("pm_demo_0002")),
      ).toBe(true);
    });
  });

  it("removes a card", async () => {
    const user = userEvent.setup();
    const fetcher = renderCardsScreen({ "DELETE /api/app/billing/cards/pm_demo_0002": {} });
    await screen.findByText("Default");

    await user.click(screen.getByRole("button", { name: "Remove card: visa •••• 0002" }));

    await waitFor(() => {
      expect(fetcher.calls.some((call) => call.method === "DELETE")).toBe(true);
    });
  });
});
