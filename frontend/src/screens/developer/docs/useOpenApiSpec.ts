import { useQuery } from "@tanstack/react-query";

import { useFetcher } from "@/api/client";
import type { Fetch, Result } from "@/types";

import type { OpenApiDocument } from "./rules";

const OPENAPI_SPEC_PATH = "/openapi.v3.json";
const SPEC_LOAD_ERROR_MSG = "Could not load the API reference. Try again.";

export function useOpenApiSpec() {
  const fetcher = useFetcher();

  return useQuery({ queryFn: () => fetchOpenApiSpec(fetcher), queryKey: [OPENAPI_SPEC_PATH] });
}

async function fetchOpenApiSpec(fetcher: Fetch): Promise<Result<OpenApiDocument>> {
  let response: Response;
  try {
    response = await fetcher(OPENAPI_SPEC_PATH);
  } catch {
    return { message: SPEC_LOAD_ERROR_MSG, status: "ERROR" };
  }
  if (!response.ok) {
    return { message: SPEC_LOAD_ERROR_MSG, status: "ERROR" };
  }

  try {
    return { data: (await response.json()) as OpenApiDocument, status: "OK" };
  } catch {
    return { message: SPEC_LOAD_ERROR_MSG, status: "ERROR" };
  }
}
