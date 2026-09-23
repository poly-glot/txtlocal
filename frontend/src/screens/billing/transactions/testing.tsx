import { fakeFetch } from "@/test/fakeFetch";
import type { FakeFetch } from "@/test/fakeFetch";
import { TRANSACTIONS_PAGE, TRANSACTIONS_ROUTE } from "@/test/fixtures/billing";
import { ACCOUNT_SETTINGS } from "@/test/fixtures/identity";
import { renderWithProviders } from "@/test/render";

import { TransactionsScreen } from "./TransactionsScreen";

export function renderTransactionsScreen(routes: Record<string, unknown> = {}): FakeFetch {
  const fetcher = fakeFetch({
    "GET /api/app/account/settings": ACCOUNT_SETTINGS,
    [TRANSACTIONS_ROUTE]: TRANSACTIONS_PAGE,
    ...routes,
  });
  renderWithProviders(<TransactionsScreen />, { fetcher });

  return fetcher;
}
