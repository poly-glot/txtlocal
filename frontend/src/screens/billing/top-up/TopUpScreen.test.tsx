import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { useApiQuery } from "@/api/queries";
import { fakeFetch, field, refusal } from "@/test/fakeFetch";
import { PACKAGES, SUMMARY } from "@/test/fixtures/billing";
import { ME } from "@/test/fixtures/identity";
import { renderWithProviders } from "@/test/render";
import { stubLocation } from "@/test/signIn";

import { TopUpScreen } from "./TopUpScreen";
import { renderTopUpScreen } from "./testing";

const rateLines = () =>
  screen.getAllByText("/ SMS", { exact: false }).map((line) => line.textContent);

function BalanceReader() {
  useApiQuery("get", "/api/app/me");

  return null;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("TopUpScreen", () => {
  it("heads the page with the balance in pounds", async () => {
    renderTopUpScreen();

    expect(
      await screen.findByRole("heading", { level: 2, name: "Current credit balance: £1.96 GBP" }),
    ).toBeInTheDocument();
  });

  it("shows that auto recharge is off", async () => {
    renderTopUpScreen();

    expect(await screen.findByText("Auto Recharge OFF")).toBeInTheDocument();
  });

  it("shows that auto recharge is on", async () => {
    renderTopUpScreen({ "GET /api/app/billing/summary": { ...SUMMARY, autoRecharge: true } });

    expect(await screen.findByText("Auto Recharge ON")).toBeInTheDocument();
  });

  it("explains what the credit pays for", async () => {
    renderTopUpScreen();

    expect(
      await screen.findByText(
        "Use your credit for any txtlocal product, including dedicated numbers. Prices are shown in British Pounds.",
      ),
    ).toBeInTheDocument();
  });

  it("shows the credit boost rate per SMS", async () => {
    renderTopUpScreen();

    await screen.findByText("Credit boost");

    expect(rateLines()).toContain("£0.0750 / SMS");
  });

  it("shows each boost with its estimate for the priced country", async () => {
    renderTopUpScreen();

    expect(await screen.findByRole("button", { name: "Top-up £10" })).toBeInTheDocument();
    expect(screen.getByText("~ 133 SMS to United Kingdom")).toBeInTheDocument();
  });

  it("describes each pack", async () => {
    renderTopUpScreen();

    expect(
      await screen.findByRole("heading", { level: 4, name: "Growth pack" }),
    ).toBeInTheDocument();
    expect(rateLines()).toContain("£0.0387 / SMS");
    expect(screen.getByText("Save 14%")).toBeInTheDocument();
    expect(screen.getByText("of credit", { exact: false })).toHaveTextContent("£349.00 of credit");
    expect(screen.getByText("~ 4,650 SMS to United Kingdom")).toBeInTheDocument();
  });

  it("prices the packages for the United Kingdom", async () => {
    const fetcher = renderTopUpScreen();
    await screen.findByRole("button", { name: "Top-up £10" });

    expect(fetcher.calls.map((call) => call.path)).toContain(
      "/api/app/billing/packages?country=GB",
    );
  });

  it("sends the browser to checkout when a pack is bought", async () => {
    const user = userEvent.setup();
    stubLocation();
    const fetcher = renderTopUpScreen({
      "POST /api/app/billing/top-ups": {
        checkoutUrl: "https://pay.test/session/pack",
        topUpId: "tu-2",
      },
    });

    await user.click(await screen.findByRole("button", { name: "Top-up Growth pack" }));

    await waitFor(() => {
      expect(window.location.href).toBe("https://pay.test/session/pack");
    });
    const post = fetcher.calls.find((call) => call.method === "POST");
    expect(field(post, "code")).toBe("GROWTH");
    expect(field(post, "kind")).toBe("PACK");
  });

  it("sends the browser to checkout when a boost is bought", async () => {
    const user = userEvent.setup();
    stubLocation();
    const CHECKOUT_URL = "https://pay.test/session/abc";
    const fetcher = renderTopUpScreen({
      "POST /api/app/billing/top-ups": { checkoutUrl: CHECKOUT_URL, topUpId: "tu-1" },
    });
    await user.click(await screen.findByRole("button", { name: "Top-up £10" }));

    await waitFor(() => {
      expect(window.location.href).toBe(CHECKOUT_URL);
    });
    const post = fetcher.calls.find((call) => call.method === "POST");
    expect(field(post, "code")).toBe("BOOST_10");
    expect(field(post, "kind")).toBe("BOOST");
  });

  it("shows the credited amount once a redirected top-up is confirmed paid", async () => {
    renderTopUpScreen(
      { "GET /api/app/billing/top-ups/tu-1": { creditedMicro: 10_000_000, status: "PAID" } },
      "/billing/top-up?topup=tu-1",
    );

    expect(await screen.findByText(/credited to your balance/)).toBeInTheDocument();
  });

  it("refreshes the balance once a redirected top-up is confirmed paid", async () => {
    const fetcher = fakeFetch({
      "GET /api/app/billing/packages?country=GB": PACKAGES,
      "GET /api/app/billing/summary": SUMMARY,
      "GET /api/app/billing/top-ups/tu-1": { creditedMicro: 10_000_000, status: "PAID" },
      "GET /api/app/me": ME,
    });
    renderWithProviders(
      <>
        <TopUpScreen />
        <BalanceReader />
      </>,
      { fetcher, route: "/billing/top-up?topup=tu-1" },
    );

    await screen.findByText(/credited to your balance/);

    await waitFor(() => {
      expect(fetcher.calls.filter((call) => call.path === "/api/app/me")).toHaveLength(2);
    });
  });

  it("renders the server's refusal verbatim", async () => {
    renderTopUpScreen({
      "GET /api/app/billing/packages?country=GB": refusal(500, "Something went wrong on our side"),
    });

    expect(await screen.findByRole("alert")).toHaveTextContent("Something went wrong on our side");
  });
});
