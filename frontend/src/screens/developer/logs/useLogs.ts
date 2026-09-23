import { keepPreviousData, useQuery } from "@tanstack/react-query";

import { callApi, useFetcher } from "@/api/client";
import { apiKey } from "@/api/queries";

import type { LogsFilterState } from "./rules";
import { logsQueryOf } from "./rules";

export function useLogs(filters: LogsFilterState) {
  const fetcher = useFetcher();

  return useQuery({
    placeholderData: keepPreviousData,
    queryFn: () =>
      callApi(fetcher, "get", "/api/app/developer/logs", {
        params: { query: logsQueryOf(filters, new Date()) },
      }),
    queryKey: apiKey("get", "/api/app/developer/logs", filters),
  });
}
