import { QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider, createBrowserRouter } from "react-router";

import { createQueryClient } from "@/api/queries";

import { appRoutes } from "./routes";

const queryClient = createQueryClient();
const router = createBrowserRouter(appRoutes());

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  );
}
