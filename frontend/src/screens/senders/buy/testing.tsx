import { fakeFetch } from "@/test/fakeFetch";
import type { FakeFetch } from "@/test/fakeFetch";
import { CATALOGUE_PAGE, DEDICATED_NUMBER, DEDICATED_SENDER } from "@/test/fixtures/senders";
import { renderWithProviders } from "@/test/render";

import { BuyANumberScreen } from "./BuyANumberScreen";

export function renderBuyANumber(routes: Record<string, unknown> = {}): FakeFetch {
  const fetcher = fakeFetch({
    "GET /api/app/numbers?country=GB&page=1&useFor=SMS": CATALOGUE_PAGE,
    [`POST /api/app/numbers/${encodeURIComponent(DEDICATED_NUMBER)}/buy`]: DEDICATED_SENDER,
    ...routes,
  });
  renderWithProviders(<BuyANumberScreen />, { fetcher });

  return fetcher;
}
