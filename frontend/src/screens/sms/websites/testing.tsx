import { fakeFetch } from "@/test/fakeFetch";
import type { FakeFetch } from "@/test/fakeFetch";
import { WEBSITE } from "@/test/fixtures/automation";
import { renderWithProviders } from "@/test/render";

import { WebsitesScreen } from "./WebsitesScreen";

export function renderWebsites(routes: Record<string, unknown> = {}): FakeFetch {
  const fetcher = fakeFetch({ "GET /api/app/websites": [WEBSITE], ...routes });
  renderWithProviders(<WebsitesScreen />, { fetcher });

  return fetcher;
}
