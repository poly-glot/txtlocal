import { fakeFetch } from "@/test/fakeFetch";
import type { FakeFetch } from "@/test/fakeFetch";
import { DEFAULT_RULE, DELIVERY_RULE, OPT_OUT_RULE } from "@/test/fixtures/automation";
import { EXAMPLE_LIST, OPT_OUT_LIST } from "@/test/fixtures/contacts";
import { OVERVIEW } from "@/test/fixtures/senders";
import { renderWithProviders } from "@/test/render";

import { WebhooksScreen } from "./WebhooksScreen";

export function renderWebhooks(routes: Record<string, unknown> = {}): FakeFetch {
  const fetcher = fakeFetch({
    "GET /api/app/lists": [EXAMPLE_LIST, OPT_OUT_LIST],
    "GET /api/app/rules/delivery": [DELIVERY_RULE],
    "GET /api/app/rules/inbound": [OPT_OUT_RULE, DEFAULT_RULE],
    "GET /api/app/senders": OVERVIEW,
    ...routes,
  });
  renderWithProviders(<WebhooksScreen />, { fetcher });

  return fetcher;
}
