import { fakeFetch } from "@/test/fakeFetch";
import type { FakeFetch } from "@/test/fakeFetch";
import { GENERAL } from "@/test/fixtures/billing";
import { renderWithProviders } from "@/test/render";

import { GeneralScreen } from "./GeneralScreen";

export function renderGeneralScreen(routes: Record<string, unknown> = {}): FakeFetch {
  const fetcher = fakeFetch({ "GET /api/app/billing/general": GENERAL, ...routes });
  renderWithProviders(<GeneralScreen />, { fetcher });

  return fetcher;
}
