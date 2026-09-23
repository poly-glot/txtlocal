import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { fakeFetch, refusal } from "@/test/fakeFetch";
import type { FakeFetch } from "@/test/fakeFetch";
import { FAILED_ROW, LOGS } from "@/test/fixtures/developer";
import { ACCOUNT_SETTINGS } from "@/test/fixtures/identity";
import { renderWithProviders } from "@/test/render";
import type { Fetch } from "@/types";

import { ApiLogsScreen } from "./ApiLogsScreen";
import { renderApiLogsScreen, sentence } from "./testing";

const A_MINUTE_LATER = new Date("2026-09-20T12:01:00.000Z");
const LOGS_PATH = "/api/app/developer/logs";
const NOW = new Date("2026-09-20T12:00:00.000Z");
const TIMEOUT_MSG = "The log search took too long, try a narrower range";
const WEEK_PATH = `${LOGS_PATH}?since=2026-09-13T12%3A00%3A00.000Z&until=2026-09-20T12%3A00%3A00.000Z`;

const logsRequests = (fetcher: FakeFetch) =>
  fetcher.calls.filter((call) => call.path.startsWith(LOGS_PATH));

function withWeekPending(fetcher: FakeFetch): Fetch {
  return (input, init) =>
    (input instanceof Request ? input.url : String(input)).includes("since=")
      ? new Promise<Response>(() => undefined)
      : fetcher(input, init);
}

describe("ApiLogsScreen", () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  it("says it is loading until the logs arrive", () => {
    renderApiLogsScreen();

    expect(screen.getByText("Loading…")).toBeInTheDocument();
  });

  it("shows the tiles and rows from the fixture", async () => {
    renderApiLogsScreen();

    expect(await screen.findByText(sentence("2 Total requests"))).toBeInTheDocument();
    expect(screen.getByText(sentence("1 Successful"))).toBeInTheDocument();
    expect(screen.getByText(sentence("1 Failed"))).toBeInTheDocument();
    expect(screen.getByText("req-1")).toBeInTheDocument();
    expect(screen.getByText("req-2")).toBeInTheDocument();
  });

  it("shows the empty state with a link to Quick SMS when there are no rows", async () => {
    renderApiLogsScreen({
      "GET /api/app/developer/logs": {
        ...LOGS,
        rows: [],
        tiles: { failed: 0, successful: 0, total: 0 },
      },
    });

    const link = await screen.findByRole("link", { name: "your first message" });
    expect(link).toHaveAttribute("href", "/sms/quick");
    expect(link.closest("p")).toHaveTextContent(
      "No SMS activity yet. Kick things off — send your first message.",
    );
  });

  it("renders a query timeout refusal verbatim", async () => {
    renderApiLogsScreen({ [`GET ${LOGS_PATH}`]: refusal(504, TIMEOUT_MSG) });

    expect(await screen.findByRole("alert")).toHaveTextContent(TIMEOUT_MSG);
  });

  it("keeps a dismissed refusal away while the next range loads", async () => {
    const user = userEvent.setup();
    const answered = fakeFetch({
      "GET /api/app/account/settings": ACCOUNT_SETTINGS,
      [`GET ${LOGS_PATH}`]: refusal(504, TIMEOUT_MSG),
    });
    renderWithProviders(<ApiLogsScreen />, { fetcher: withWeekPending(answered) });
    const alert = await screen.findByRole("alert");
    await user.click(within(alert).getByRole("button", { name: "Dismiss" }));

    await user.selectOptions(screen.getByLabelText("Date Range"), "Last 7 days");

    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("asks for the last seven days as one closed window", async () => {
    vi.useFakeTimers({ now: NOW, toFake: ["Date"] });
    const user = userEvent.setup();
    renderApiLogsScreen({ [`GET ${WEEK_PATH}`]: { ...LOGS, rows: [FAILED_ROW] } });
    await screen.findByText("req-1");

    await user.selectOptions(screen.getByLabelText("Date Range"), "Last 7 days");

    expect(await screen.findByText("1 Results")).toBeInTheDocument();
  });

  it("pages through the last seven days without asking for them again", async () => {
    vi.useFakeTimers({ now: NOW, toFake: ["Date"] });
    const user = userEvent.setup();
    const fetcher = renderApiLogsScreen({ [`GET ${WEEK_PATH}`]: { ...LOGS, resultsPerPage: 1 } });
    await screen.findByText("req-1");
    await user.selectOptions(screen.getByLabelText("Date Range"), "Last 7 days");
    await screen.findByText("Page 1 of 2");

    vi.setSystemTime(A_MINUTE_LATER);
    await user.click(screen.getByRole("button", { name: "Next" }));

    expect(screen.getByText("req-2")).toBeInTheDocument();
    expect(logsRequests(fetcher)).toHaveLength(2);
  });

  it("keeps the subaccount filter typeable while the logs reload", async () => {
    const user = userEvent.setup();
    renderApiLogsScreen({
      [`GET ${LOGS_PATH}?subaccount=u`]: LOGS,
      [`GET ${LOGS_PATH}?subaccount=us`]: LOGS,
    });

    await user.type(await screen.findByLabelText("Subaccount"), "us");

    expect(screen.getByLabelText("Subaccount")).toHaveValue("us");
  });
});
