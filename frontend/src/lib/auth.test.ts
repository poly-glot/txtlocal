import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { callApi } from "@/api/client";
import { fakeFetch, field, json } from "@/test/fakeFetch";
import { TEST_TOKENS, navigatedTo, signInForTest, stubLocation } from "@/test/signIn";

import {
  SIGN_IN_FAILED_MSG,
  completeSignIn,
  isSignedIn,
  redirectToSignIn,
  refreshAccessToken,
  signOut,
} from "./auth";

const BASE64URL_43 = /^[A-Za-z0-9_-]{43}$/;

async function challengeOf(verifier: unknown): Promise<string> {
  const text = typeof verifier === "string" ? verifier : "";
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));

  return btoa(String.fromCharCode(...new Uint8Array(digest)))
    .replaceAll("+", "-")
    .replaceAll("/", "_")
    .replace(/=+$/, "");
}

beforeEach(() => {
  sessionStorage.clear();
  stubLocation();
  signOut();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("redirectToSignIn", () => {
  it("sends the browser to the authorize endpoint with an S256 challenge", async () => {
    const assign = stubLocation();

    await redirectToSignIn("/contacts");

    const url = navigatedTo(assign);
    expect(url.pathname).toBe("/oauth2/authorize");
    expect(url.searchParams.get("code_challenge_method")).toBe("S256");
    expect(url.searchParams.get("code_challenge")).toMatch(BASE64URL_43);
    expect(url.searchParams.get("redirect_uri")).toBe("http://localhost:3000/auth/callback");
    expect(url.searchParams.get("response_type")).toBe("code");
  });
});

describe("completeSignIn", () => {
  it("exchanges the code, opens the session and returns where to go", async () => {
    const assign = stubLocation();
    await redirectToSignIn("/contacts?q=1");
    const state = navigatedTo(assign).searchParams.get("state") ?? "";
    const fetcher = fakeFetch({ "POST /api/app/session": {}, "POST /oauth2/token": TEST_TOKENS });

    const result = await completeSignIn(new URLSearchParams({ code: "abc", state }), fetcher);

    expect(result).toEqual({ data: "/contacts?q=1", status: "OK" });
    const [exchange, session] = fetcher.calls;
    expect(exchange?.body).toMatchObject({
      code: "abc",
      grant_type: "authorization_code",
      redirect_uri: "http://localhost:3000/auth/callback",
    });
    expect(session).toMatchObject({
      authorization: "Bearer access-1",
      body: { idToken: "id-1" },
      path: "/api/app/session",
    });
    expect(isSignedIn()).toBe(true);
  });

  it("sends a verifier whose digest is the challenge it advertised, then forgets it", async () => {
    const assign = stubLocation();
    await redirectToSignIn("/");
    const state = navigatedTo(assign).searchParams.get("state") ?? "";
    const fetcher = fakeFetch({ "POST /api/app/session": {}, "POST /oauth2/token": TEST_TOKENS });

    await completeSignIn(new URLSearchParams({ code: "abc", state }), fetcher);

    const verifier = field(fetcher.calls[0], "code_verifier");
    expect(await challengeOf(verifier)).toBe(
      navigatedTo(assign).searchParams.get("code_challenge"),
    );
    expect(sessionStorage.length).toBe(0);
  });

  it("refuses a callback whose state does not match", async () => {
    stubLocation();
    await redirectToSignIn("/");

    const result = await completeSignIn(
      new URLSearchParams({ code: "abc", state: "forged" }),
      fakeFetch({}),
    );

    expect(result).toEqual({ message: SIGN_IN_FAILED_MSG, status: "ERROR" });
  });

  it("refuses when the token endpoint refuses the code", async () => {
    const assign = stubLocation();
    await redirectToSignIn("/");
    const state = navigatedTo(assign).searchParams.get("state") ?? "";

    const result = await completeSignIn(
      new URLSearchParams({ code: "abc", state }),
      fakeFetch({ "POST /oauth2/token": json(400, { error: "invalid_grant" }) }),
    );

    expect(result).toEqual({ message: SIGN_IN_FAILED_MSG, status: "ERROR" });
    expect(isSignedIn()).toBe(false);
  });

  it("surfaces the server sentence when the session cannot be opened", async () => {
    const assign = stubLocation();
    await redirectToSignIn("/");
    const state = navigatedTo(assign).searchParams.get("state") ?? "";

    const result = await completeSignIn(
      new URLSearchParams({ code: "abc", state }),
      fakeFetch({
        "POST /api/app/session": json(403, { message: "Sign in to continue" }),
        "POST /oauth2/token": TEST_TOKENS,
      }),
    );

    expect(result).toEqual({ message: "Sign in to continue", status: "ERROR" });
    expect(isSignedIn()).toBe(false);
  });
});

describe("refreshAccessToken", () => {
  it("swaps the access token through the token endpoint", async () => {
    await signInForTest();
    const fetcher = fakeFetch({
      "POST /oauth2/token": { access_token: "access-2", id_token: "id-2" },
    });

    expect(await refreshAccessToken(fetcher)).toBe("access-2");
    expect(fetcher.calls[0]?.body).toMatchObject({
      grant_type: "refresh_token",
      refresh_token: "refresh-1",
    });
  });

  it("sends the browser back to sign-in when the exchange fails", async () => {
    await signInForTest();
    const assign = stubLocation("/contacts", "?q=1");

    const fresh = await refreshAccessToken(fakeFetch({ "POST /oauth2/token": json(400, {}) }));

    expect(fresh).toBeUndefined();
    expect(isSignedIn()).toBe(false);
    expect(navigatedTo(assign).pathname).toBe("/oauth2/authorize");
  });

  it("is what request uses after a 401", async () => {
    await signInForTest();
    const fetcher = fakeFetch({
      "GET /api/app/me": json(401, { message: "Sign in to continue" }),
      "POST /oauth2/token": { access_token: "access-2", id_token: "id-2" },
    });

    await callApi(fetcher, "get", "/api/app/me");

    expect(fetcher.calls.map((call) => call.authorization)).toEqual([
      "Bearer access-1",
      null,
      "Bearer access-2",
    ]);
  });
});

describe("signOut", () => {
  it("forgets the session and sends the browser to the logout endpoint", async () => {
    await signInForTest();
    const assign = stubLocation();

    signOut();

    expect(isSignedIn()).toBe(false);
    const url = navigatedTo(assign);
    expect(url.pathname).toBe("/logout");
    expect(url.searchParams.get("logout_uri")).toBe("http://localhost:3000/");
  });
});
