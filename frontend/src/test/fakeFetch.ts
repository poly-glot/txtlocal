import type { Fetch } from "@/types";

export interface Call {
  authorization: string | null;
  body: unknown;
  method: string;
  path: string;
}

export interface FakeFetch extends Fetch {
  calls: Call[];
}

export function fakeFetch(routes: Record<string, unknown>): FakeFetch {
  const calls: Call[] = [];
  const fetcher = async (input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
    const call = await callOf(input, init);
    calls.push(call);

    const answer = routes[`${call.method} ${call.path}`];
    if (answer instanceof Response) {
      return answer.clone();
    }
    if (answer === undefined) {
      return json(404, { message: `No fake route for ${call.method} ${call.path}` });
    }

    return json(200, answer);
  };

  return Object.assign(fetcher, { calls });
}

export function json(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    headers: { "content-type": "application/json" },
    status,
  });
}

export function refusal(status: number, message: string): Response {
  return json(status, { code: "REFUSED", message });
}

async function callOf(input: RequestInfo | URL, init?: RequestInit): Promise<Call> {
  const path = pathOf(input);
  if (input instanceof Request) {
    return {
      authorization: input.headers.get("authorization"),
      body: await requestBodyOf(input),
      method: input.method,
      path,
    };
  }

  return {
    authorization: new Headers(init?.headers).get("authorization"),
    body: bodyOf(init?.body),
    method: init?.method ?? "GET",
    path,
  };
}

function pathOf(input: RequestInfo | URL): string {
  const url = input instanceof Request ? input.url : input.toString();

  return url.replace(/^https?:\/\/[^/]+/, "");
}

async function requestBodyOf(request: Request): Promise<unknown> {
  const text = await request.text();

  return text === "" ? undefined : JSON.parse(text);
}

function bodyOf(body: BodyInit | null | undefined): unknown {
  if (typeof body === "string") {
    return JSON.parse(body);
  }
  if (body instanceof URLSearchParams) {
    return Object.fromEntries(body);
  }

  return body;
}

export function field(call: Call | undefined, name: string): unknown {
  const body = call?.body;

  return typeof body === "object" && body !== null && name in body
    ? Reflect.get(body, name)
    : undefined;
}
