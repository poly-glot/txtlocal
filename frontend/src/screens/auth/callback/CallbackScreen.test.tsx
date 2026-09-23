import { screen } from "@testing-library/react";
import { Route, Routes } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { redirectToSignIn } from "@/lib/auth";
import { fakeFetch } from "@/test/fakeFetch";
import { renderWithProviders } from "@/test/render";
import { TEST_TOKENS, navigatedTo, stubLocation } from "@/test/signIn";

import { CallbackScreen } from "./CallbackScreen";

function renderCallback(query: string) {
  const fetcher = fakeFetch({ "POST /api/app/session": {}, "POST /oauth2/token": TEST_TOKENS });
  renderWithProviders(
    <Routes>
      <Route element={<CallbackScreen />} path="/auth/callback" />
      <Route element={<p>Contacts page</p>} path="/contacts" />
    </Routes>,
    { fetcher, route: `/auth/callback?${query}` },
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("CallbackScreen", () => {
  it("finishes sign-in and returns the user to where they were", async () => {
    const assign = stubLocation();
    await redirectToSignIn("/contacts");
    const state = navigatedTo(assign).searchParams.get("state") ?? "";

    renderCallback(new URLSearchParams({ code: "abc", state }).toString());

    expect(await screen.findByText("Contacts page")).toBeInTheDocument();
  });

  it("offers to try again when the sign-in fails", async () => {
    stubLocation();
    await redirectToSignIn("/contacts");

    renderCallback("code=abc&state=forged");

    expect(await screen.findByRole("alert")).toHaveTextContent("Sign-in failed. Try again.");
    expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
  });
});
