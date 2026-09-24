import { screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { navigatedTo, stubLocation } from "@/test/signIn";

import { renderShell } from "./testing";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("Shell", () => {
  it("sends a signed-out visitor to sign in without rendering the page", async () => {
    const assign = stubLocation();

    renderShell("/contacts?page=2");

    await waitFor(() => {
      expect(assign).toHaveBeenCalledOnce();
    });
    expect(navigatedTo(assign).pathname).toBe("/oauth2/authorize");
    expect(screen.queryByText("Page body")).not.toBeInTheDocument();
  });

  it("shows a signed-out visitor at the home page the landing page", async () => {
    const assign = stubLocation();

    renderShell("/");

    expect(
      await screen.findByRole("heading", {
        level: 1,
        name: "Send SMS your customers actually read",
      }),
    ).toBeInTheDocument();
    expect(assign).not.toHaveBeenCalled();
  });
});
