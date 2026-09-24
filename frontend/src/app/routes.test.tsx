import { QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { RouterProvider, createMemoryRouter } from "react-router";
import { beforeEach, describe, expect, it } from "vitest";

import { FetcherContext } from "@/api/client";
import { createQueryClient } from "@/api/queries";
import { fakeFetch } from "@/test/fakeFetch";
import { ME } from "@/test/fixtures/identity";
import { signInForTest } from "@/test/signIn";

import { appRoutes } from "./routes";

function renderApp(route: string) {
  const router = createMemoryRouter(appRoutes(), {
    initialEntries: [route],
  });
  render(
    <FetcherContext value={fakeFetch({ "GET /api/app/me": ME })}>
      <QueryClientProvider client={createQueryClient()}>
        <RouterProvider router={router} />
      </QueryClientProvider>
    </FetcherContext>,
  );
}

beforeEach(async () => {
  await signInForTest();
});

describe("appRoutes", () => {
  it("opens Billing on the Top Up Account tab", async () => {
    renderApp("/billing");

    expect(await screen.findByRole("tab", { name: "Top Up Account" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    expect(screen.getByRole("heading", { level: 1, name: "Billing" })).toBeInTheDocument();
  });

  it("sends an unknown path home", async () => {
    renderApp("/nowhere");

    expect(await screen.findByRole("heading", { level: 1, name: "Home" })).toBeInTheDocument();
  });
});
