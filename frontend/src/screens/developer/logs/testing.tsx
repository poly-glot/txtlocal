import { fakeFetch } from "@/test/fakeFetch";
import type { FakeFetch } from "@/test/fakeFetch";
import { LOGS } from "@/test/fixtures/developer";
import { ACCOUNT_SETTINGS } from "@/test/fixtures/identity";
import { renderWithProviders } from "@/test/render";

import { ApiLogsScreen } from "./ApiLogsScreen";

export function renderApiLogsScreen(routes: Record<string, unknown> = {}): FakeFetch {
  const fetcher = fakeFetch({
    "GET /api/app/account/settings": ACCOUNT_SETTINGS,
    "GET /api/app/developer/logs": LOGS,
    ...routes,
  });
  renderWithProviders(<ApiLogsScreen />, { fetcher });

  return fetcher;
}

export function sentence(text: string) {
  return (_content: string, element: Element | null) => element?.textContent === text;
}
