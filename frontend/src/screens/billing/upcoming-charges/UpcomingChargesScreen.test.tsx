import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { refusal } from "@/test/fakeFetch";

import { renderUpcomingChargesScreen } from "./testing";

describe("UpcomingChargesScreen", () => {
  it("lists every dedicated number due a charge", async () => {
    renderUpcomingChargesScreen();

    expect(await screen.findByText("+447700900001")).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "NEXT CHARGE" })).toBeInTheDocument();
    expect(screen.getByText("£2.65")).toBeInTheDocument();
  });

  it("shows the empty state in place of the table when nothing is due", async () => {
    renderUpcomingChargesScreen({ "GET /api/app/billing/upcoming-charges": [] });

    expect(await screen.findByText("There's nothing here right now")).toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });

  it("renders the server's refusal verbatim", async () => {
    renderUpcomingChargesScreen({
      "GET /api/app/billing/upcoming-charges": refusal(500, "Something went wrong on our side"),
    });

    expect(await screen.findByRole("alert")).toHaveTextContent("Something went wrong on our side");
  });
});
