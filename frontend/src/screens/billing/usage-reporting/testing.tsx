import { fakeFetch } from "@/test/fakeFetch";
import type { FakeFetch } from "@/test/fakeFetch";
import { REPORTING_NOW, REPORTING_PAGE, REPORTING_ROUTE } from "@/test/fixtures/analytics";
import { ACCOUNT_USERS } from "@/test/fixtures/identity";
import { renderWithProviders } from "@/test/render";

import { UsageReportingScreen } from "./UsageReportingScreen";

export function renderUsageReportingScreen(routes: Record<string, unknown> = {}): FakeFetch {
  const fetcher = fakeFetch({
    "GET /api/app/account/users": ACCOUNT_USERS,
    [REPORTING_ROUTE]: REPORTING_PAGE,
    ...routes,
  });
  renderWithProviders(<UsageReportingScreen now={REPORTING_NOW} />, { fetcher });

  return fetcher;
}
