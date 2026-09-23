import { OPENAPI_FIXTURE } from "@/test/fixtures/developer";
import { fakeFetch } from "@/test/fakeFetch";
import type { FakeFetch } from "@/test/fakeFetch";
import { renderWithProviders } from "@/test/render";

import { ApiDocsScreen } from "./ApiDocsScreen";

export function renderApiDocsScreen(routes: Record<string, unknown> = {}): FakeFetch {
  const fetcher = fakeFetch({ "GET /openapi.v3.json": OPENAPI_FIXTURE, ...routes });
  renderWithProviders(<ApiDocsScreen />, { fetcher });

  return fetcher;
}
