import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { refusal } from "@/test/fakeFetch";
import { TRANSACTIONS_PAGE, TRANSACTIONS_ROUTE } from "@/test/fixtures/billing";

import { renderTransactionsScreen } from "./testing";

const NEXT_PAGE_ROUTE = "GET /api/app/billing/transactions?cursor=cursor-2&order=desc";
const OLDEST_FIRST_ROUTE = "GET /api/app/billing/transactions?order=asc";

const OLDER_TOP_UP = {
  amountMicro: 30_000_000,
  balanceAfterMicro: 42_000_000,
  createdAt: "2026-09-19T10:00:00Z",
  creditedMicro: 30_000_000,
  entryId: "entry-2",
  kind: "TOPUP",
  paidMicro: 28_000_000,
  ref: "top-up-2",
  stripeInvoiceNumber: null,
  stripeInvoiceUrl: null,
} as const;

describe("TransactionsScreen", () => {
  it("links the invoice number to Stripe's hosted invoice", async () => {
    renderTransactionsScreen();

    expect(
      await screen.findByRole("link", { name: "Invoice DEMO-1 (opens in a new tab)" }),
    ).toHaveAttribute("href", "https://example.test/invoice/1");
  });

  it("marks each top-up as paid", async () => {
    renderTransactionsScreen();

    expect(await screen.findByText("Paid")).toBeInTheDocument();
  });

  it("shows the credited amount signed as a credit", async () => {
    renderTransactionsScreen();

    expect(await screen.findByText("£10.00")).toBeInTheDocument();
    expect(screen.getByText("£10.00").parentElement).toHaveTextContent("+£10.00");
  });

  it("loads the next page of transactions on request", async () => {
    const user = userEvent.setup();
    renderTransactionsScreen({
      [TRANSACTIONS_ROUTE]: { ...TRANSACTIONS_PAGE, nextCursor: "cursor-2" },
      [NEXT_PAGE_ROUTE]: { items: [OLDER_TOP_UP], nextCursor: null },
    });
    await screen.findByText("£10.00");

    await user.click(screen.getByRole("button", { name: "Load more" }));

    expect(await screen.findByText("£30.00")).toBeInTheDocument();
  });

  it("lists newest first by default", async () => {
    renderTransactionsScreen();

    expect(await screen.findByRole("columnheader", { name: "DATE" })).toHaveAttribute(
      "aria-sort",
      "descending",
    );
  });

  it("reloads oldest first from the first page when DATE is pressed", async () => {
    const user = userEvent.setup();
    renderTransactionsScreen({
      [TRANSACTIONS_ROUTE]: { ...TRANSACTIONS_PAGE, nextCursor: "cursor-2" },
      [OLDEST_FIRST_ROUTE]: { items: [OLDER_TOP_UP], nextCursor: null },
    });
    await screen.findByText("£10.00");

    await user.click(screen.getByRole("button", { name: "DATE" }));

    expect(await screen.findByText("£30.00")).toBeInTheDocument();
    expect(screen.queryByText("£10.00")).not.toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "DATE" })).toHaveAttribute(
      "aria-sort",
      "ascending",
    );
  });

  it.each(["INVOICE #", "STATUS", "AMOUNT"])("offers no sort on %s", async (header) => {
    renderTransactionsScreen();
    await screen.findByText("£10.00");

    expect(screen.queryByRole("button", { name: header })).not.toBeInTheDocument();
  });

  it("hides load more on the last page", async () => {
    renderTransactionsScreen();
    await screen.findByText("£10.00");

    expect(screen.queryByRole("button", { name: "Load more" })).not.toBeInTheDocument();
  });

  it("shows the empty state in place of the table with no transactions", async () => {
    renderTransactionsScreen({
      [TRANSACTIONS_ROUTE]: { items: [], nextCursor: null },
    });

    expect(await screen.findByText("No transactions")).toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });

  it("renders the server's refusal verbatim", async () => {
    renderTransactionsScreen({
      [TRANSACTIONS_ROUTE]: refusal(500, "Something went wrong on our side"),
    });

    expect(await screen.findByRole("alert")).toHaveTextContent("Something went wrong on our side");
  });
});
