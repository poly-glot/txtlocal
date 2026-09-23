import { QueryClientProvider } from "@tanstack/react-query";
import { render, renderHook } from "@testing-library/react";
import type { RenderHookResult, RenderResult } from "@testing-library/react";
import type { ReactElement, ReactNode } from "react";
import { MemoryRouter } from "react-router";

import { FetcherContext } from "@/api/client";
import { createQueryClient } from "@/api/queries";
import type { Fetch } from "@/types";

import { fakeFetch } from "./fakeFetch";

interface ProviderOptions {
  fetcher?: Fetch;
  route?: string;
}

const testQueryClient = () => createQueryClient({ defaultOptions: { queries: { retry: false } } });

function providers({ fetcher = fakeFetch({}), route = "/" }: ProviderOptions) {
  const queryClient = testQueryClient();

  return ({ children }: { children: ReactNode }) => (
    <FetcherContext value={fetcher}>
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={[route]}>{children}</MemoryRouter>
      </QueryClientProvider>
    </FetcherContext>
  );
}

export function renderWithProviders(ui: ReactElement, options: ProviderOptions = {}): RenderResult {
  return render(ui, { wrapper: providers(options) });
}

export function renderHookWithProviders<Value>(
  hook: () => Value,
  options: ProviderOptions = {},
): RenderHookResult<Value, unknown> {
  return renderHook(hook, { wrapper: providers(options) });
}
