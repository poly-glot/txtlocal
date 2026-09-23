import { QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import { RouterProvider, createMemoryRouter } from "react-router";

import { FetcherContext } from "@/api/client";
import type { MeView } from "@/api/generated/dashboard";
import { createQueryClient } from "@/api/queries";
import { fakeFetch } from "@/test/fakeFetch";
import { ME } from "@/test/fixtures/identity";

import { Shell } from "./Shell";

export function renderShell(route = "/", me: MeView = ME) {
  const router = createMemoryRouter(
    [
      {
        children: [{ element: <p>Page body</p>, path: "*" }],
        element: <Shell />,
      },
    ],
    { initialEntries: [route] },
  );
  render(
    <FetcherContext value={fakeFetch({ "GET /api/app/me": me })}>
      <QueryClientProvider client={createQueryClient()}>
        <RouterProvider router={router} />
      </QueryClientProvider>
    </FetcherContext>,
  );
}
