import { fakeFetch } from "@/test/fakeFetch";
import type { FakeFetch } from "@/test/fakeFetch";
import { EXAMPLE_LIST, OPT_OUT_LIST } from "@/test/fixtures/contacts";
import { ACCOUNT_SETTINGS } from "@/test/fixtures/identity";
import { QUOTE, TEMPLATE } from "@/test/fixtures/messaging";
import { OVERVIEW } from "@/test/fixtures/senders";
import { renderWithProviders } from "@/test/render";

import { QuickSendScreen } from "./QuickSendScreen";

export function renderQuickSms(
  routes: Record<string, unknown> = {},
  route = "/sms/quick",
): FakeFetch {
  const fetcher = quickSendFetch(routes);
  renderWithProviders(<QuickSendScreen kind="SMS" />, { fetcher, route });

  return fetcher;
}

export function renderQuickMms(): FakeFetch {
  const fetcher = quickSendFetch({});
  renderWithProviders(<QuickSendScreen kind="MMS" />, { fetcher, route: "/mms/quick" });

  return fetcher;
}

function quickSendFetch(routes: Record<string, unknown>): FakeFetch {
  return fakeFetch({
    "GET /api/app/account/settings": ACCOUNT_SETTINGS,
    "GET /api/app/lists": [EXAMPLE_LIST, OPT_OUT_LIST],
    "GET /api/app/senders": OVERVIEW,
    "GET /api/app/templates": [TEMPLATE],
    "POST /api/app/messages/quote": QUOTE,
    "POST /api/app/messages/send": { campaignId: "campaign-1" },
    ...routes,
  });
}
