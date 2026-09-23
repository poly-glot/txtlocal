import { attachBearer, callApi } from "@/api/client";
import type { Fetch, Result } from "@/types";

import { CALLBACK_PATH } from "./paths";

const CLIENT_ID = import.meta.env.VITE_COGNITO_CLIENT_ID ?? "";
const DOMAIN = import.meta.env.VITE_COGNITO_DOMAIN ?? "";
const HANDOFF_KEY = "txtlocal.signIn";
const SCOPE = "email openid";
const TOKEN_BYTES = 32;

export const SIGN_IN_FAILED_MSG = "Sign-in failed. Try again.";

interface Handoff {
  returnTo: string;
  state: string;
  verifier: string;
}

interface TokenResponse {
  access_token: string;
  id_token: string;
  refresh_token?: string;
}

interface Tokens {
  accessToken: string;
  idToken: string;
  refreshToken: string | undefined;
}

let tokens: Tokens | undefined;

export function isSignedIn(): boolean {
  return tokens !== undefined;
}

export async function redirectToSignIn(returnTo: string): Promise<void> {
  const handoff: Handoff = { returnTo, state: randomToken(), verifier: randomToken() };
  sessionStorage.setItem(HANDOFF_KEY, JSON.stringify(handoff));

  window.location.assign(await authorizeUrl(handoff));
}

export async function completeSignIn(
  params: URLSearchParams,
  fetcher: Fetch = fetch,
): Promise<Result<string>> {
  const handoff = takeHandoff();
  const code = params.get("code");
  if (handoff === undefined || code === null || params.get("state") !== handoff.state) {
    return { message: SIGN_IN_FAILED_MSG, status: "ERROR" };
  }

  const exchanged = await postTokenForm(
    {
      client_id: CLIENT_ID,
      code,
      code_verifier: handoff.verifier,
      grant_type: "authorization_code",
      redirect_uri: callbackUrl(),
    },
    fetcher,
  );
  if (exchanged.status === "ERROR") {
    return exchanged;
  }
  tokens = tokensOf(exchanged.data);

  const session = await callApi(fetcher, "post", "/api/app/session", {
    body: { idToken: tokens.idToken },
  });
  if (session.status === "ERROR") {
    tokens = undefined;
    return session;
  }

  return { data: handoff.returnTo, status: "OK" };
}

export async function refreshAccessToken(fetcher: Fetch = fetch): Promise<string | undefined> {
  const refreshToken = tokens?.refreshToken;
  const refreshed =
    refreshToken === undefined
      ? undefined
      : await postTokenForm(
          { client_id: CLIENT_ID, grant_type: "refresh_token", refresh_token: refreshToken },
          fetcher,
        );
  if (refreshed?.status !== "OK") {
    tokens = undefined;
    await redirectToSignIn(currentPath());
    return undefined;
  }

  tokens = { ...tokensOf(refreshed.data), refreshToken };

  return tokens.accessToken;
}

export function signOut(): void {
  tokens = undefined;
  window.location.assign(logoutUrl());
}

async function postTokenForm(
  form: Record<string, string>,
  fetcher: Fetch,
): Promise<Result<TokenResponse>> {
  let payload: unknown;
  try {
    const response = await fetcher(`${DOMAIN}/oauth2/token`, {
      body: new URLSearchParams(form),
      method: "POST",
    });
    payload = response.ok ? await response.json() : null;
  } catch {
    payload = null;
  }

  return isTokenResponse(payload)
    ? { data: payload, status: "OK" }
    : { message: SIGN_IN_FAILED_MSG, status: "ERROR" };
}

async function authorizeUrl(handoff: Handoff): Promise<string> {
  const query = new URLSearchParams({
    client_id: CLIENT_ID,
    code_challenge: await challengeOf(handoff.verifier),
    code_challenge_method: "S256",
    redirect_uri: callbackUrl(),
    response_type: "code",
    scope: SCOPE,
    state: handoff.state,
  });

  return `${DOMAIN}/oauth2/authorize?${query.toString()}`;
}

function logoutUrl(): string {
  const query = new URLSearchParams({
    client_id: CLIENT_ID,
    logout_uri: `${window.location.origin}/`,
  });

  return `${DOMAIN}/logout?${query.toString()}`;
}

function callbackUrl(): string {
  return `${window.location.origin}${CALLBACK_PATH}`;
}

function currentPath(): string {
  return `${window.location.pathname}${window.location.search}`;
}

function takeHandoff(): Handoff | undefined {
  const raw = sessionStorage.getItem(HANDOFF_KEY);
  sessionStorage.removeItem(HANDOFF_KEY);
  if (raw === null) {
    return undefined;
  }

  const parsed: unknown = JSON.parse(raw);

  return isHandoff(parsed) ? parsed : undefined;
}

function tokensOf(data: TokenResponse): Tokens {
  return {
    accessToken: data.access_token,
    idToken: data.id_token,
    refreshToken: data.refresh_token,
  };
}

function randomToken(): string {
  return base64Url(crypto.getRandomValues(new Uint8Array(TOKEN_BYTES)));
}

async function challengeOf(verifier: string): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(verifier));

  return base64Url(new Uint8Array(digest));
}

function base64Url(bytes: Uint8Array): string {
  return btoa(String.fromCharCode(...bytes))
    .replaceAll("+", "-")
    .replaceAll("/", "_")
    .replace(/=+$/, "");
}

function isHandoff(value: unknown): value is Handoff {
  return (
    isRecord(value) &&
    typeof value.returnTo === "string" &&
    typeof value.state === "string" &&
    typeof value.verifier === "string"
  );
}

function isTokenResponse(value: unknown): value is TokenResponse {
  return (
    isRecord(value) && typeof value.access_token === "string" && typeof value.id_token === "string"
  );
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

attachBearer({ refresh: refreshAccessToken, token: () => tokens?.accessToken });
