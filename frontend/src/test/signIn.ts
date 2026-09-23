import { vi } from "vitest";

import { completeSignIn, redirectToSignIn } from "@/lib/auth";

import { fakeFetch } from "./fakeFetch";

export const ORIGIN = "http://localhost:3000";
export const TEST_TOKENS = {
  access_token: "access-1",
  id_token: "id-1",
  refresh_token: "refresh-1",
};

export function stubLocation(
  pathname = "/",
  search = "",
): ReturnType<typeof vi.fn<(url: string) => void>> {
  const assign = vi.fn<(url: string) => void>();
  vi.stubGlobal("location", { assign, origin: ORIGIN, pathname, search });

  return assign;
}

export function navigatedTo(assign: ReturnType<typeof stubLocation>): URL {
  return new URL(assign.mock.calls[0]?.[0] ?? "", ORIGIN);
}

export async function signInForTest(): Promise<void> {
  const assign = stubLocation();
  await redirectToSignIn("/");
  const state = navigatedTo(assign).searchParams.get("state") ?? "";

  const result = await completeSignIn(
    new URLSearchParams({ code: "test-code", state }),
    fakeFetch({ "POST /api/app/session": {}, "POST /oauth2/token": TEST_TOKENS }),
  );
  vi.unstubAllGlobals();
  if (result.status === "ERROR") {
    throw new Error(result.message);
  }
}
