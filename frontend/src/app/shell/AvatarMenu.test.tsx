import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ME } from "@/test/fixtures/identity";
import { navigatedTo, signInForTest, stubLocation } from "@/test/signIn";

import { renderShell } from "./testing";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("AvatarMenu", () => {
  beforeEach(async () => {
    await signInForTest();
  });

  it("opens the avatar menu with the user id and the account pages", async () => {
    const user = userEvent.setup();
    renderShell();

    await user.click(await screen.findByLabelText("Account menu"));

    expect(screen.getByText("User ID: user-1")).toBeInTheDocument();
    for (const label of [
      "My Profile",
      "Account Settings",
      "Messaging Settings",
      "Billing",
      "Global Sending",
      "Reseller Clients",
      "Reseller Settings",
      "Referrals",
    ]) {
      expect(screen.getByRole("link", { name: label })).toBeInTheDocument();
    }
    expect(screen.getByRole("button", { name: "Logout" })).toBeInTheDocument();
  });

  it("closes the avatar menu when the user clicks elsewhere", async () => {
    const user = userEvent.setup();
    renderShell();
    await user.click(await screen.findByLabelText("Account menu"));

    await user.click(screen.getByText("Page body"));

    expect(screen.getByRole("link", { name: "My Profile" })).not.toBeVisible();
  });

  it("closes the avatar menu on Escape", async () => {
    const user = userEvent.setup();
    renderShell();
    await user.click(await screen.findByLabelText("Account menu"));

    await user.keyboard("{Escape}");

    expect(screen.getByRole("link", { name: "My Profile" })).not.toBeVisible();
  });

  it("hides Billing from a sub-account", async () => {
    renderShell("/", { ...ME, role: "SUB" });

    await screen.findByLabelText("Account menu");

    expect(screen.queryByRole("link", { name: "Billing" })).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "My Profile" })).toBeInTheDocument();
  });

  it("logs out through the identity provider", async () => {
    const user = userEvent.setup();
    renderShell();
    await screen.findByLabelText("Account menu");
    const assign = stubLocation();

    await user.click(screen.getByRole("button", { name: "Logout" }));

    expect(navigatedTo(assign).pathname).toBe("/logout");
  });
});
