import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { HISTORY } from "@/test/fixtures/messaging";

import { renderHistory } from "./testing";

describe("HistoryScreen", () => {
  it("names the six columns the history shows", async () => {
    renderHistory();

    for (const header of ["USERNAME", "DATE", "FROM", "TO", "STATUS", "BODY"]) {
      expect(await screen.findByRole("button", { name: header })).toBeInTheDocument();
    }
  });

  it("promises four months of history", async () => {
    renderHistory();

    expect(
      await screen.findByText("Historical data is retained for 4 months."),
    ).toBeInTheDocument();
  });

  it("shows how many rows a page holds", async () => {
    renderHistory();

    expect(await screen.findByText("Show 20 Entries")).toBeInTheDocument();
  });

  it("names the filters above the table", async () => {
    renderHistory();

    expect(await screen.findByLabelText("From")).toHaveAttribute("placeholder", "Enter Date");
    expect(screen.getByRole("heading", { name: "SMS History" })).toBeInTheDocument();
    expect(screen.getByLabelText("Search")).toHaveAttribute(
      "placeholder",
      "Search in international format",
    );
    expect(screen.getByLabelText("Field")).toHaveValue("TO");
    expect(screen.getByRole("button", { name: "Last 7 days" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Last 30 days" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Clear" })).toBeInTheDocument();
  });

  it("badges a delivered message and a failed one", async () => {
    renderHistory();

    expect(await screen.findByText("Delivered")).toBeInTheDocument();
    expect(screen.getByText("Failed")).toBeInTheDocument();
  });

  it("shows the date in the account's time zone", async () => {
    renderHistory();

    expect(await screen.findAllByText("19/09/2026, 15:13")).toHaveLength(2);
  });

  it("says there are no results when the page is empty", async () => {
    renderHistory({ "GET /api/app/messages?field=TO": { cursor: null, items: [] } });

    expect(await screen.findByText("No results")).toBeInTheDocument();
  });

  it("opens a row with its parts, price and failure reason", async () => {
    const user = userEvent.setup();
    renderHistory();

    await user.click(await screen.findByRole("button", { name: "Open message to +447400123100" }));
    const dialog = await screen.findByRole("dialog", { name: "Message detail" });

    expect(within(dialog).getByText("The handset rejected the message")).toBeInTheDocument();
    expect(within(dialog).getByText("£0.0427")).toBeInTheDocument();
    expect(within(dialog).getByText("fake-1")).toBeInTheDocument();
    expect(within(dialog).getByText("Parts")).toBeInTheDocument();
    expect(within(dialog).getByText("Provider id")).toBeInTheDocument();
    expect(within(dialog).getByText("Failure reason")).toBeInTheDocument();
    expect(within(dialog).getByRole("button", { name: "CLOSE" })).toBeInTheDocument();
  });

  it("asks the server for a single day when Today is chosen", async () => {
    const user = userEvent.setup();
    const fetcher = renderHistory();
    await screen.findByText("Delivered");

    await user.click(screen.getByRole("button", { name: "Today" }));

    const asked = fetcher.calls.findLast((call) => call.path.startsWith("/api/app/messages?"));
    const params = new URLSearchParams(asked?.path.split("?")[1] ?? "");
    expect(params.get("from")).toBe(params.get("to"));
  });

  it("searches the chosen field in international format", async () => {
    const user = userEvent.setup();
    const fetcher = renderHistory();
    await screen.findByText("Delivered");

    await user.type(screen.getByLabelText("Search"), "+447400123105{Enter}");

    const asked = fetcher.calls.findLast((call) => call.path.startsWith("/api/app/messages?"));
    expect(asked?.path).toBe("/api/app/messages?field=TO&q=%2B447400123105");
  });

  it("keeps the search it ran in the search box", async () => {
    const user = userEvent.setup();
    const fetcher = renderHistory({ "GET /api/app/messages?field=TO&q=%2B447400123105": HISTORY });
    await screen.findByText("Delivered");

    await user.type(screen.getByLabelText("Search"), "+447400123105{Enter}");
    await waitFor(() => {
      expect(fetcher.calls.at(-1)?.path).toBe("/api/app/messages?field=TO&q=%2B447400123105");
    });

    expect(screen.getByLabelText("Search")).toHaveValue("+447400123105");
  });

  it("keeps Next disabled on the last page", async () => {
    renderHistory();

    await screen.findByText("Delivered");

    expect(screen.getByRole("button", { name: "Next" })).toBeDisabled();
  });

  it("asks for the next page with the cursor the server returned", async () => {
    const user = userEvent.setup();
    const fetcher = renderHistory({
      "GET /api/app/messages?field=TO": { ...HISTORY, cursor: "cursor-2" },
      "GET /api/app/messages?cursor=cursor-2&field=TO": HISTORY,
    });
    await screen.findByText("Delivered");

    await user.click(screen.getByRole("button", { name: "Next" }));

    expect(await screen.findByRole("button", { name: "Previous" })).toBeEnabled();
    expect(fetcher.calls.at(-1)?.path).toBe("/api/app/messages?cursor=cursor-2&field=TO");
  });

  it("exports the current filter as CSV", async () => {
    const user = userEvent.setup();
    const fetcher = renderHistory();
    await screen.findByText("Delivered");

    await user.click(screen.getByRole("button", { name: "EXPORT ▾" }));
    await user.click(screen.getByRole("button", { name: "CSV" }));

    const exported = fetcher.calls.find((call) => call.path.startsWith("/api/app/messages/export"));
    expect(exported?.path).toBe("/api/app/messages/export?field=TO");
  });
});
