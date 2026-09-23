import { screen } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";

import { ME } from "@/test/fixtures/identity";
import { signInForTest } from "@/test/signIn";

import { renderShell } from "./testing";

const TRIAL_BANNER = "Only 12 days to use your free trial credit. Top up for full access.";

describe("TopBar", () => {
  beforeEach(async () => {
    await signInForTest();
  });

  it("shows the trial banner with the days left and the top-up link", async () => {
    renderShell();

    expect(await screen.findByText(TRIAL_BANNER)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Top up now" })).toHaveAttribute(
      "href",
      "/billing/top-up",
    );
  });

  it("drops the banner once the account has topped up", async () => {
    renderShell("/", { ...ME, hasToppedUp: true });

    await screen.findByText("Balance:", { exact: false });

    expect(screen.queryByText(TRIAL_BANNER)).not.toBeInTheDocument();
  });

  it("shows the balance to two places", async () => {
    renderShell();

    expect(await screen.findByText("Balance:", { exact: false })).toHaveTextContent(
      "Balance: £2.00",
    );
  });

  it("titles the page after the route", async () => {
    renderShell("/sms/quick");

    expect(await screen.findByRole("heading", { level: 1, name: "Quick SMS" })).toBeInTheDocument();
    expect(screen.getByText("Page body")).toBeInTheDocument();
  });
});
