import { fakeFetch } from "@/test/fakeFetch";
import type { FakeFetch } from "@/test/fakeFetch";
import { TEMPLATE } from "@/test/fixtures/messaging";
import { renderWithProviders } from "@/test/render";

import { TemplatesScreen } from "./TemplatesScreen";

export function renderTemplates(routes: Record<string, unknown> = {}): FakeFetch {
  const fetcher = fakeFetch({
    "GET /api/app/templates": [TEMPLATE],
    "POST /api/app/templates": TEMPLATE,
    ...routes,
  });
  renderWithProviders(<TemplatesScreen />, { fetcher });

  return fetcher;
}
