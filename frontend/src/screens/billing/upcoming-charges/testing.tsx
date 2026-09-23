import { fakeFetch } from "@/test/fakeFetch";
import type { FakeFetch } from "@/test/fakeFetch";
import { UPCOMING_CHARGES } from "@/test/fixtures/billing";
import { ACCOUNT_SETTINGS } from "@/test/fixtures/identity";
import { renderWithProviders } from "@/test/render";

import { UpcomingChargesScreen } from "./UpcomingChargesScreen";

export function renderUpcomingChargesScreen(routes: Record<string, unknown> = {}): FakeFetch {
  const fetcher = fakeFetch({
    "GET /api/app/account/settings": ACCOUNT_SETTINGS,
    "GET /api/app/billing/upcoming-charges": UPCOMING_CHARGES,
    ...routes,
  });
  renderWithProviders(<UpcomingChargesScreen />, { fetcher });

  return fetcher;
}
