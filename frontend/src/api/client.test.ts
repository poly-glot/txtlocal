import { afterEach, describe, expect, it } from "vitest";

import { fakeFetch, json } from "@/test/fakeFetch";

import { attachBearer, callApi, searchOf } from "./client";

const answering = (outcome: Error | Response) => (): Promise<Response> =>
  outcome instanceof Error ? Promise.reject(outcome) : Promise.resolve(outcome);

const answeringByToken =
  (accepted: string): typeof fetch =>
  (input) => {
    const authorization = input instanceof Request ? input.headers.get("authorization") : null;

    return Promise.resolve(
      authorization === `Bearer ${accepted}`
        ? json(200, { ok: true })
        : json(401, { message: "Sign in to continue" }),
    );
  };

afterEach(() => {
  attachBearer();
});

describe("callApi", () => {
  it("returns OK with the parsed body on 2xx", async () => {
    const result = await callApi(answering(json(200, { ok: true })), "get", "/api/app/me");

    expect(result).toEqual({ data: { ok: true }, status: "OK" });
  });

  it("returns OK with no data when the server answers 204", async () => {
    const result = await callApi(
      answering(new Response(null, { status: 204 })),
      "delete",
      "/api/app/senders/{senderId}",
      { params: { path: { senderId: "s1" } } },
    );

    expect(result).toEqual({ data: undefined, status: "OK" });
  });

  it("returns the raw text when the caller asked for text", async () => {
    const csv = "date,to,status\n2026-09-19,+447400123105,DELIVERED\n";
    const result = await callApi(
      answering(new Response(csv, { headers: { "content-type": "text/csv" }, status: 200 })),
      "get",
      "/api/app/lists/{listId}/export",
      { params: { path: { listId: "list-1" } }, parseAs: "text" },
    );

    expect(result).toEqual({ data: csv, status: "OK" });
  });

  it("returns the server refusal verbatim on 4xx", async () => {
    const result = await callApi(
      answering(json(402, { code: "INSUFFICIENT_BALANCE", message: "Your balance is £0.00" })),
      "post",
      "/api/app/billing/cards",
    );

    expect(result).toEqual({ message: "Your balance is £0.00", status: "ERROR" });
  });

  it("returns the generic sentence when a failure carries no message", async () => {
    const result = await callApi(
      answering(json(502, "bad gateway")),
      "post",
      "/api/app/billing/cards",
    );

    expect(result).toEqual({ message: "Something went wrong. Try again.", status: "ERROR" });
  });

  it("returns the generic sentence when a 2xx body is not JSON", async () => {
    const result = await callApi(
      answering(new Response("<html>", { status: 200 })),
      "post",
      "/api/app/billing/cards",
    );

    expect(result).toEqual({ message: "Something went wrong. Try again.", status: "ERROR" });
  });

  it("returns the network sentence when fetch rejects", async () => {
    const result = await callApi(answering(new TypeError("offline")), "get", "/api/app/me");

    expect(result).toEqual({
      message: "Could not reach the server. Check your connection and try again.",
      status: "ERROR",
    });
  });

  it("attaches the bearer token", async () => {
    attachBearer({ refresh: () => Promise.resolve(undefined), token: () => "current" });

    const result = await callApi(answeringByToken("current"), "get", "/api/app/me");

    expect(result).toEqual({ data: { ok: true }, status: "OK" });
  });

  it("retries once with a fresh token after a 401", async () => {
    attachBearer({ refresh: () => Promise.resolve("fresh"), token: () => "stale" });

    const result = await callApi(answeringByToken("fresh"), "get", "/api/app/me");

    expect(result).toEqual({ data: { ok: true }, status: "OK" });
  });

  it("returns the refusal when no fresh token arrives", async () => {
    attachBearer({ refresh: () => Promise.resolve(undefined), token: () => "stale" });

    const result = await callApi(answeringByToken("fresh"), "get", "/api/app/me");

    expect(result).toEqual({ message: "Sign in to continue", status: "ERROR" });
  });

  it("encodes path parameters and leaves out empty query values", async () => {
    const fetcher = fakeFetch({});

    await callApi(fetcher, "get", "/api/app/conversations/{peer}", {
      params: { path: { peer: "+447400123123" } },
    });
    await callApi(fetcher, "get", "/api/app/lists", { params: { query: { q: "" } } });

    expect(fetcher.calls.map((call) => call.path)).toEqual([
      "/api/app/conversations/%2B447400123123",
      "/api/app/lists",
    ]);
  });
});

describe("searchOf", () => {
  it.each([
    { expected: "", label: "nothing for an empty query", query: {} },
    {
      expected: "",
      label: "drops empty, null and undefined values",
      query: { a: "", b: null, c: undefined },
    },
    {
      expected: "limit=20&q=sam",
      label: "sorts the names",
      query: { q: "sam", limit: 20 },
    },
    {
      expected: "product=SMS&product=MMS",
      label: "repeats a list",
      query: { product: ["SMS", "MMS"] },
    },
    { expected: "q=a+b%26c", label: "encodes values", query: { q: "a b&c" } },
  ] as const)("$label", ({ expected, query }) => {
    expect(searchOf(query)).toBe(expected);
  });
});
