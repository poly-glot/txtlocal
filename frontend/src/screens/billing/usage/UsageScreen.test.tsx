import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { USAGE_MONTH_ROUTE } from "@/test/fixtures/analytics";
import { refusal } from "@/test/fakeFetch";

import { renderUsageScreen } from "./testing";

describe("UsageScreen", () => {
  it("shows usage rows with resolved usernames and formatted costs", async () => {
    renderUsageScreen();

    const table = await screen.findByRole("table");
    expect(within(table).getByText("demo@txtlocal.local")).toBeInTheDocument();
    expect(within(table).getByText("sub@txtlocal.local")).toBeInTheDocument();
    expect(within(table).getByText("£0.0427")).toBeInTheDocument();
    expect(within(table).getByText("£0.0854")).toBeInTheDocument();
  });

  it("filters the table by product", async () => {
    const user = userEvent.setup();
    renderUsageScreen();
    const table = await screen.findByRole("table");
    await within(table).findByText("demo@txtlocal.local");

    await user.selectOptions(screen.getByLabelText("Product"), "MMS as link");

    expect(within(table).queryByText("demo@txtlocal.local")).not.toBeInTheDocument();
    expect(within(table).getByText("sub@txtlocal.local")).toBeInTheDocument();
  });

  it("filters the table by username", async () => {
    const user = userEvent.setup();
    renderUsageScreen();
    const table = await screen.findByRole("table");
    await within(table).findByText("demo@txtlocal.local");

    await user.selectOptions(screen.getByLabelText("Username"), "demo@txtlocal.local");

    expect(within(table).getByText("demo@txtlocal.local")).toBeInTheDocument();
    expect(within(table).queryByText("sub@txtlocal.local")).not.toBeInTheDocument();
  });

  it("shows an empty state with no usage", async () => {
    renderUsageScreen({ [USAGE_MONTH_ROUTE]: { rows: [] } });

    expect(await screen.findByText("No usage for this month.")).toBeInTheDocument();
  });

  it("renders the server's refusal verbatim", async () => {
    renderUsageScreen({
      [USAGE_MONTH_ROUTE]: refusal(500, "Something went wrong on our side"),
    });

    expect(await screen.findByRole("alert")).toHaveTextContent("Something went wrong on our side");
  });
});
