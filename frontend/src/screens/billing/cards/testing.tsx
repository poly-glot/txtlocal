import { fakeFetch } from "@/test/fakeFetch";
import type { FakeFetch } from "@/test/fakeFetch";
import { CARDS } from "@/test/fixtures/billing";
import { renderWithProviders } from "@/test/render";

import { CardsScreen } from "./CardsScreen";

export function renderCardsScreen(routes: Record<string, unknown> = {}): FakeFetch {
  const fetcher = fakeFetch({ "GET /api/app/billing/cards": CARDS, ...routes });
  renderWithProviders(<CardsScreen />, { fetcher });

  return fetcher;
}
