import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { refusal } from "@/test/fakeFetch";
import { CATALOGUE_NUMBER, DEDICATED_NUMBER } from "@/test/fixtures/senders";

import { renderBuyANumber } from "./testing";

describe("BuyANumberScreen", () => {
  it("lists the catalogue for the default filters", async () => {
    renderBuyANumber();

    expect(
      await screen.findByText(
        "Send messages globally and boost customer recognition with purchased numbers.",
      ),
    ).toBeInTheDocument();
    expect(await screen.findByText(DEDICATED_NUMBER)).toBeInTheDocument();
  });

  it("refetches the catalogue when the contains filter changes", async () => {
    const user = userEvent.setup();
    const fetcher = renderBuyANumber({
      "GET /api/app/numbers?contains=39&country=GB&page=1&useFor=SMS": {
        numbers: [CATALOGUE_NUMBER],
        page: 1,
        totalPages: 1,
      },
    });
    await screen.findByText(DEDICATED_NUMBER);

    await user.type(screen.getByLabelText("Filter results"), "39");

    expect(
      fetcher.calls.some(
        (call) => call.path === "/api/app/numbers?contains=39&country=GB&page=1&useFor=SMS",
      ),
    ).toBe(true);
  });

  it("opens a confirmation naming the number and its price before buying", async () => {
    const user = userEvent.setup();
    renderBuyANumber();
    await screen.findByText(DEDICATED_NUMBER);

    await user.click(screen.getByRole("button", { name: `Buy ${DEDICATED_NUMBER}` }));

    const dialog = screen.getByRole("dialog", { name: `Rent ${DEDICATED_NUMBER}` });
    expect(dialog).toHaveTextContent("charged now and every month from your balance");
    expect(dialog).toHaveTextContent("£2.65");
  });

  it("buys the number and closes the confirmation", async () => {
    const user = userEvent.setup();
    const fetcher = renderBuyANumber();
    await screen.findByText(DEDICATED_NUMBER);

    await user.click(screen.getByRole("button", { name: `Buy ${DEDICATED_NUMBER}` }));
    await user.click(screen.getByRole("button", { name: "Buy" }));

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(
      fetcher.calls.some(
        (call) => call.path === `/api/app/numbers/${encodeURIComponent(DEDICATED_NUMBER)}/buy`,
      ),
    ).toBe(true);
  });

  it("renders the server's refusal verbatim and leaves the dialog open", async () => {
    const user = userEvent.setup();
    renderBuyANumber({
      [`POST /api/app/numbers/${encodeURIComponent(DEDICATED_NUMBER)}/buy`]: refusal(
        400,
        "Top up to rent a number",
      ),
    });
    await screen.findByText(DEDICATED_NUMBER);

    await user.click(screen.getByRole("button", { name: `Buy ${DEDICATED_NUMBER}` }));
    await user.click(screen.getByRole("button", { name: "Buy" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Top up to rent a number");
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });

  it("names the page of the catalogue it shows", async () => {
    renderBuyANumber({
      "GET /api/app/numbers?country=GB&page=1&useFor=SMS": {
        numbers: [CATALOGUE_NUMBER],
        page: 1,
        totalPages: 2,
      },
    });

    expect(await screen.findByText("Page 1 of 2")).toBeInTheDocument();
  });

  it("fetches the page the user picks", async () => {
    const user = userEvent.setup();
    const fetcher = renderBuyANumber({
      "GET /api/app/numbers?country=GB&page=1&useFor=SMS": {
        numbers: [CATALOGUE_NUMBER],
        page: 1,
        totalPages: 2,
      },
      "GET /api/app/numbers?country=GB&page=2&useFor=SMS": {
        numbers: [CATALOGUE_NUMBER],
        page: 2,
        totalPages: 2,
      },
    });
    await screen.findByText(DEDICATED_NUMBER);

    await user.click(screen.getByRole("button", { name: "Next page" }));

    expect(await screen.findByText("Page 2 of 2")).toBeInTheDocument();
    expect(
      fetcher.calls.some((call) => call.path === "/api/app/numbers?country=GB&page=2&useFor=SMS"),
    ).toBe(true);
  });
});
