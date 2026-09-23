import { fakeFetch } from "@/test/fakeFetch";
import type { FakeFetch } from "@/test/fakeFetch";
import { ACCOUNT_SETTINGS } from "@/test/fixtures/identity";
import { FAILED_ROW, HISTORY } from "@/test/fixtures/messaging";
import { renderWithProviders } from "@/test/render";

import { HistoryScreen } from "./HistoryScreen";

export function renderHistory(routes: Record<string, unknown> = {}): FakeFetch {
  const fetcher = fakeFetch({
    "GET /api/app/account/settings": ACCOUNT_SETTINGS,
    "GET /api/app/messages?field=TO": HISTORY,
    "GET /api/app/messages/message-2": FAILED_ROW,
    ...routes,
  });
  renderWithProviders(<HistoryScreen />, { fetcher });

  return fetcher;
}
