import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { REPORTING_EXPORT_PATH, REPORTING_ROUTE } from "@/test/fixtures/analytics";
import { refusal } from "@/test/fakeFetch";

import { renderUsageReportingScreen } from "./testing";

describe("UsageReportingScreen", () => {
  it("shows reporting rows with resolved usernames, country and formatted amounts", async () => {
    renderUsageReportingScreen();

    const table = await screen.findByRole("table");
    expect(within(table).getByText("demo@txtlocal.local")).toBeInTheDocument();
    expect(within(table).getByText("19/09/2026")).toBeInTheDocument();
    expect(within(table).getByText("🇬🇧 United Kingdom")).toBeInTheDocument();
    expect(within(table).getByText("£0.0427")).toBeInTheDocument();
    expect(within(table).getByText("£0.04")).toBeInTheDocument();
    expect(screen.getByText("1 results")).toBeInTheDocument();
  });

  it("shows an empty state with no results", async () => {
    renderUsageReportingScreen({
      [REPORTING_ROUTE]: { page: 1, pageSize: 10, rows: [], totalResults: 0 },
    });

    expect(await screen.findByText("No results for this filter.")).toBeInTheDocument();
  });

  it("renders the server's refusal as a dismissable notice while keeping the filters", async () => {
    renderUsageReportingScreen({
      [REPORTING_ROUTE]: refusal(400, "the date range spans at most 4 months"),
    });

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "the date range spans at most 4 months",
    );
    expect(screen.getByLabelText("From")).toBeInTheDocument();
  });

  it("keeps every keystroke in a filter while the filtered page loads", async () => {
    const user = userEvent.setup();
    renderUsageReportingScreen();
    await screen.findByRole("table");

    await user.type(screen.getByLabelText("Countries"), "GB");

    expect(screen.getByLabelText("Countries")).toHaveValue("GB");
  });

  it("exports the current filters as csv", async () => {
    const user = userEvent.setup();
    const fetcher = renderUsageReportingScreen();
    await screen.findByRole("table");

    await user.click(screen.getByRole("button", { name: "EXPORT" }));

    const call = fetcher.calls.find((one) =>
      one.path.startsWith("/api/app/analytics/reporting/export"),
    );
    expect(call?.path).toBe(REPORTING_EXPORT_PATH);
  });
});
