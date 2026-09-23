import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { refusal } from "@/test/fakeFetch";
import { REPORT, SENT } from "@/test/fixtures/campaigns";

import { renderCampaigns } from "../testing";

const SENT_PAGE = { cursor: null, items: [SENT] };

async function openReport(user: ReturnType<typeof userEvent.setup>): Promise<void> {
  await user.click(await screen.findByRole("button", { name: `Open ${SENT.name}` }));
}

describe("CampaignReportView", () => {
  it("names the campaign it reports on", async () => {
    const user = userEvent.setup();
    renderCampaigns({ "GET /api/app/campaigns?kind=SMS": SENT_PAGE });

    await openReport(user);

    expect(await screen.findByRole("heading", { name: SENT.name })).toBeInTheDocument();
  });

  it("counts what happened to the campaign", async () => {
    const user = userEvent.setup();
    renderCampaigns({ "GET /api/app/campaigns?kind=SMS": SENT_PAGE });

    await openReport(user);

    expect(await screen.findByText("Recipients")).toBeInTheDocument();
    expect(screen.getByText("Refused")).toBeInTheDocument();
    expect(screen.getByText("Delivered")).toBeInTheDocument();
    expect(screen.getByText("Undelivered")).toBeInTheDocument();
  });

  it("shows zero clicks before any link has been clicked", async () => {
    const user = userEvent.setup();
    renderCampaigns({ "GET /api/app/campaigns?kind=SMS": SENT_PAGE });

    await openReport(user);

    const clicksTerm = await screen.findByText("Clicks");
    expect(clicksTerm.nextElementSibling).toHaveTextContent("0");
  });

  it("says when clicks are counted", async () => {
    const user = userEvent.setup();
    renderCampaigns({ "GET /api/app/campaigns?kind=SMS": SENT_PAGE });

    await openReport(user);

    expect(await screen.findByText("Clicks are counted nightly.")).toBeInTheDocument();
  });

  it("shows the clicks analytics reports", async () => {
    const user = userEvent.setup();
    renderCampaigns({
      "GET /api/app/campaigns?kind=SMS": SENT_PAGE,
      "GET /api/app/campaigns/campaign-3/report": { ...REPORT, clicks: 7 },
    });

    await openReport(user);

    expect(await screen.findByText("7")).toBeInTheDocument();
  });

  it("returns to the list", async () => {
    const user = userEvent.setup();
    renderCampaigns({ "GET /api/app/campaigns?kind=SMS": SENT_PAGE });

    await openReport(user);
    await user.click(await screen.findByRole("button", { name: "Back to campaigns" }));

    expect(await screen.findByRole("heading", { name: "SMS Campaigns" })).toBeInTheDocument();
  });

  it("returns to the list from a refused report", async () => {
    const user = userEvent.setup();
    renderCampaigns({
      "GET /api/app/campaigns?kind=SMS": SENT_PAGE,
      "GET /api/app/campaigns/campaign-3/report": refusal(404, "Campaign not found"),
    });

    await openReport(user);
    await screen.findByRole("alert");
    await user.click(screen.getByRole("button", { name: "Back to campaigns" }));

    expect(await screen.findByRole("heading", { name: "SMS Campaigns" })).toBeInTheDocument();
  });

  it("renders the server's refusal of the report verbatim", async () => {
    const user = userEvent.setup();
    renderCampaigns({
      "GET /api/app/campaigns?kind=SMS": SENT_PAGE,
      "GET /api/app/campaigns/campaign-3/report": refusal(404, "Campaign not found"),
    });

    await openReport(user);

    expect(await screen.findByRole("alert")).toHaveTextContent("Campaign not found");
  });
});
