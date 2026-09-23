import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { signInForTest } from "@/test/signIn";

import { SIDEBAR, leavesOf } from "../navigation";
import { renderShell } from "./testing";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("Sidebar", () => {
  beforeEach(async () => {
    await signInForTest();
  });

  it("lists every sidebar entry", async () => {
    renderShell();
    await screen.findByText("Page body");

    for (const leaf of leavesOf(SIDEBAR)) {
      expect(screen.getAllByRole("link", { name: leaf.label }).length).toBeGreaterThan(0);
    }
  });

  it("opens only the sidebar group that holds the current route", async () => {
    renderShell("/sms/quick");
    await screen.findByText("Page body");

    expect(screen.getByRole("link", { name: "Quick SMS" })).toBeVisible();
    expect(screen.getByRole("link", { name: "Manage Senders" })).not.toBeVisible();
  });

  it("keeps a sidebar group the user opened open across navigation", async () => {
    const user = userEvent.setup();
    renderShell();
    await screen.findByText("Page body");

    await user.click(screen.getByText("Developers"));
    await user.click(screen.getByRole("link", { name: "API Logs" }));

    expect(await screen.findByRole("heading", { level: 1, name: "API Logs" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Webhooks" })).toBeVisible();
  });

  it("hides the sidebar navigation once collapsed", async () => {
    const user = userEvent.setup();
    renderShell();
    await screen.findByText("Page body");

    await user.click(screen.getByRole("button", { name: "Collapse sidebar" }));

    expect(screen.queryByRole("navigation", { name: "Main" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Expand sidebar" })).toBeInTheDocument();
  });

  it("starts with the sidebar collapsed on a narrow viewport", async () => {
    vi.stubGlobal("matchMedia", (media: string) => ({ matches: true, media }));
    renderShell();
    await screen.findByText("Page body");

    expect(screen.getByRole("button", { name: "Expand sidebar" })).toBeInTheDocument();
  });
});
