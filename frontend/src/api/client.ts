import createClient from "openapi-fetch";
import type { ClientPathsWithMethod, FetchResponse, MaybeOptionalInit } from "openapi-fetch";
import { createContext, useContext } from "react";

import type { Fetch, Result } from "@/types";

import type { ErrorBody, paths } from "./generated/dashboard";

const NETWORK_MSG = "Could not reach the server. Check your connection and try again.";
const UNAUTHORIZED_STATUS = 401;
const UNEXPECTED_MSG = "Something went wrong. Try again.";

export type Method = "delete" | "get" | "patch" | "post" | "put";
export type PathOf<M extends Method> = ClientPathsWithMethod<typeof client, M>;
export type InitOf<M extends Method, P extends PathOf<M>> = MaybeOptionalInit<paths[P], M>;
export type InitArgs<I> = undefined extends I ? [init?: I] : [init: I];
export type DataOf<M extends Method, P extends PathOf<M>, I = InitOf<M, P>> = Required<
  FetchResponse<NonNullable<paths[P][M]>, I, `${string}/${string}`>
>["data"];

export interface Bearer {
  refresh(fetcher: Fetch): Promise<string | undefined>;
  token(): string | undefined;
}

interface Outcome {
  data?: unknown;
  error?: unknown;
  response: Response;
}

class Unreachable extends Error {}

const anonymous: Bearer = { refresh: () => Promise.resolve(undefined), token: () => undefined };

let bearer = anonymous;

const client = createClient<paths>({
  baseUrl: globalThis.location.origin,
  querySerializer: searchOf,
});

export const FetcherContext = createContext<Fetch>(fetch);

export function useFetcher(): Fetch {
  return useContext(FetcherContext);
}

export function attachBearer(next: Bearer = anonymous): void {
  bearer = next;
}

export async function callApi<M extends Method, P extends PathOf<M>, I extends InitOf<M, P>>(
  fetcher: Fetch,
  method: M,
  path: P,
  ...[init]: InitArgs<I>
): Promise<Result<DataOf<M, P, I>>> {
  const send = (request: Request) => sendAuthorized(request, fetcher);

  let outcome: Outcome;
  try {
    outcome = await client.request(method, path, { ...init, fetch: send } as never);
  } catch (error) {
    return {
      message: error instanceof Unreachable ? NETWORK_MSG : UNEXPECTED_MSG,
      status: "ERROR",
    };
  }

  if (!outcome.response.ok) {
    return { message: refusalOf(outcome.error), status: "ERROR" };
  }

  return { data: outcome.data as DataOf<M, P, I>, status: "OK" };
}

export function searchOf(query: Readonly<Record<string, unknown>>): string {
  const search = new URLSearchParams();
  for (const [name, value] of Object.entries(query).sort(byName)) {
    for (const item of [value].flat()) {
      if (isSearchable(item)) {
        search.append(name, String(item));
      }
    }
  }

  return search.toString();
}

async function sendAuthorized(request: Request, fetcher: Fetch): Promise<Response> {
  const retry = request.clone();
  const response = await reach(fetcher, authorized(request, bearer.token()));
  if (response.status !== UNAUTHORIZED_STATUS) {
    return response;
  }

  const fresh = await bearer.refresh(fetcher);

  return fresh === undefined ? response : reach(fetcher, authorized(retry, fresh));
}

function authorized(request: Request, token: string | undefined): Request {
  if (token !== undefined) {
    request.headers.set("authorization", `Bearer ${token}`);
  }

  return request;
}

async function reach(fetcher: Fetch, request: Request): Promise<Response> {
  try {
    return await fetcher(request);
  } catch {
    throw new Unreachable();
  }
}

function refusalOf(error: unknown): string {
  return isRefusal(error) ? error.message : UNEXPECTED_MSG;
}

function isRefusal(value: unknown): value is Pick<ErrorBody, "message"> {
  return (
    typeof value === "object" &&
    value !== null &&
    "message" in value &&
    typeof value.message === "string"
  );
}

function byName([left]: [string, unknown], [right]: [string, unknown]): number {
  return left < right ? -1 : 1;
}

function isSearchable(value: unknown): value is boolean | number | string {
  return (
    (typeof value === "string" && value !== "") ||
    typeof value === "number" ||
    typeof value === "boolean"
  );
}
