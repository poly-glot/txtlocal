import { fakeFetch } from "@/test/fakeFetch";
import type { FakeFetch } from "@/test/fakeFetch";
import { ACCOUNT_SETTINGS } from "@/test/fixtures/identity";
import { JANE_CONVERSATION, JANE_PEER, JANE_THREAD } from "@/test/fixtures/inbox";
import { OVERVIEW } from "@/test/fixtures/senders";
import { renderWithProviders } from "@/test/render";

import { InboxScreen } from "./InboxScreen";

export function renderInbox(routes: Record<string, unknown> = {}): FakeFetch {
  const fetcher = fakeFetch({
    "GET /api/app/account/settings": ACCOUNT_SETTINGS,
    "GET /api/app/conversations?status=OPEN": { items: [JANE_CONVERSATION], nextCursor: null },
    [`GET /api/app/conversations/${encodeURIComponent(JANE_PEER)}`]: JANE_THREAD,
    "GET /api/app/senders": OVERVIEW,
    ...routes,
  });
  renderWithProviders(<InboxScreen />, { fetcher });

  return fetcher;
}
