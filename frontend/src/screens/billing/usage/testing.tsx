import { fakeFetch } from "@/test/fakeFetch";
import type { FakeFetch } from "@/test/fakeFetch";
import { REPORTING_NOW, USAGE_MONTH_ROUTE, USAGE_PAGE } from "@/test/fixtures/analytics";
import { ACCOUNT_USERS } from "@/test/fixtures/identity";
import { renderWithProviders } from "@/test/render";

import { UsageScreen } from "./UsageScreen";

export function renderUsageScreen(routes: Record<string, unknown> = {}): FakeFetch {
  const fetcher = fakeFetch({
    "GET /api/app/account/users": ACCOUNT_USERS,
    [USAGE_MONTH_ROUTE]: USAGE_PAGE,
    ...routes,
  });
  renderWithProviders(<UsageScreen now={REPORTING_NOW} />, { fetcher });

  return fetcher;
}
