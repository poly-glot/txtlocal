import { fakeFetch } from "@/test/fakeFetch";
import type { FakeFetch } from "@/test/fakeFetch";
import { PACKAGES, SUMMARY } from "@/test/fixtures/billing";
import { renderWithProviders } from "@/test/render";

import { TopUpScreen } from "./TopUpScreen";

export function renderTopUpScreen(
  routes: Record<string, unknown> = {},
  route = "/billing/top-up",
): FakeFetch {
  const fetcher = fakeFetch({
    "GET /api/app/billing/packages?country=GB": PACKAGES,
    "GET /api/app/billing/summary": SUMMARY,
    ...routes,
  });
  renderWithProviders(<TopUpScreen />, { fetcher, route });

  return fetcher;
}
