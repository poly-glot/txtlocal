import { useInfiniteQuery } from "@tanstack/react-query";

import { callApi, useFetcher } from "@/api/client";
import type { LedgerOrder, PageLedgerEntry } from "@/api/generated/dashboard";
import { apiKey } from "@/api/queries";
import type { Result } from "@/types";

const FIRST_CURSOR: string | undefined = undefined;

export function useTransactions(order: LedgerOrder) {
  const fetcher = useFetcher();

  return useInfiniteQuery({
    getNextPageParam: (lastPage: Result<PageLedgerEntry>) =>
      lastPage.status === "OK" ? (lastPage.data.nextCursor ?? undefined) : undefined,
    initialPageParam: FIRST_CURSOR,
    queryFn: ({ pageParam }) =>
      callApi(fetcher, "get", "/api/app/billing/transactions", {
        params: { query: { cursor: pageParam ?? null, order } },
      }),
    queryKey: apiKey("get", "/api/app/billing/transactions", order),
  });
}
