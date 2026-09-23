import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { refusal } from "@/test/fakeFetch";
import { DRAFT, SCHEDULED, SENT } from "@/test/fixtures/campaigns";

import { renderCampaigns } from "../testing";

const EMPTY_PAGE = { cursor: null, items: [] };

describe("CampaignList", () => {
  it("invites the first SMS campaign when there are none", async () => {
    renderCampaigns({ "GET /api/app/campaigns?kind=SMS": EMPTY_PAGE });

    expect(
      await screen.findByRole("button", { name: "CLICK HERE TO ADD YOUR FIRST SMS CAMPAIGN" }),
    ).toBeInTheDocument();
  });

  it("invites the first MMS campaign when there are none", async () => {
    renderCampaigns({ "GET /api/app/campaigns?kind=MMS": EMPTY_PAGE }, "MMS");

    expect(
      await screen.findByRole("button", { name: "CLICK HERE TO ADD YOUR FIRST MMS CAMPAIGN" }),
    ).toBeInTheDocument();
  });

  it("names the heading, the search and the five columns", async () => {
    renderCampaigns();

    expect(screen.getByRole("heading", { name: "SMS Campaigns" })).toBeInTheDocument();
    expect(await screen.findByLabelText("Search")).toHaveAttribute("placeholder", "Search...");
    expect(screen.getByRole("button", { name: "CAMPAIGN" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "STATUS" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "DATE" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "FROM" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "RECIPIENTS" })).toBeInTheDocument();
  });

  it("lists a campaign with its status, sender and recipients", async () => {
    renderCampaigns();

    expect(await screen.findByText("Summer sale")).toBeInTheDocument();
    expect(screen.getByText("Scheduled")).toBeInTheDocument();
    expect(screen.getByText("Shared Number")).toBeInTheDocument();
    expect(screen.getByText("31 Jul 2027, 23:59")).toBeInTheDocument();
  });

  it("keeps the search box while a search loads", async () => {
    const user = userEvent.setup();
    renderCampaigns({
      "GET /api/app/campaigns?kind=SMS&q=S": { cursor: null, items: [SCHEDULED] },
      "GET /api/app/campaigns?kind=SMS&q=Su": { cursor: null, items: [SCHEDULED] },
    });

    await user.type(await screen.findByLabelText("Search"), "Su");

    expect(screen.getByLabelText("Search")).toHaveValue("Su");
  });

  it("counts the entries a page shows", async () => {
    renderCampaigns();

    expect(await screen.findByText("Show 20 Entries")).toBeInTheDocument();
  });

  it("offers Cancel only while a campaign is scheduled", async () => {
    renderCampaigns({ "GET /api/app/campaigns?kind=SMS": { cursor: null, items: [SENT] } });

    expect(await screen.findByRole("button", { name: `Open ${SENT.name}` })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: `Duplicate ${SENT.name}` })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: `Cancel ${SENT.name}` })).not.toBeInTheDocument();
  });

  it("cancels a scheduled campaign", async () => {
    const user = userEvent.setup();
    const fetcher = renderCampaigns();

    await user.click(await screen.findByRole("button", { name: "Cancel Summer sale" }));

    expect(fetcher.calls.some((call) => call.path === "/api/app/campaigns/campaign-2/cancel")).toBe(
      true,
    );
  });

  it("renders the server's refusal of a cancel verbatim", async () => {
    const user = userEvent.setup();
    renderCampaigns({
      "POST /api/app/campaigns/campaign-2/cancel": refusal(409, "This campaign is already sending"),
    });

    await user.click(await screen.findByRole("button", { name: "Cancel Summer sale" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("This campaign is already sending");
  });

  it("duplicates a campaign into a new draft", async () => {
    const user = userEvent.setup();
    const fetcher = renderCampaigns();

    await user.click(await screen.findByRole("button", { name: "Duplicate Summer sale" }));

    expect(
      fetcher.calls.some((call) => call.path === "/api/app/campaigns/campaign-2/duplicate"),
    ).toBe(true);
  });

  it("opens a sent campaign on its report", async () => {
    const user = userEvent.setup();
    renderCampaigns({ "GET /api/app/campaigns?kind=SMS": { cursor: null, items: [SENT] } });

    await user.click(await screen.findByRole("button", { name: `Open ${SENT.name}` }));

    expect(await screen.findByText("Delivered")).toBeInTheDocument();
  });

  it("opens a draft campaign in the editor", async () => {
    const user = userEvent.setup();
    renderCampaigns({ "GET /api/app/campaigns?kind=SMS": { cursor: null, items: [DRAFT] } });

    await user.click(await screen.findByRole("button", { name: `Open ${DRAFT.name}` }));

    expect(await screen.findByLabelText("Campaign name")).toHaveValue("Helloworld");
  });

  it("renders the server's refusal of the list verbatim", async () => {
    renderCampaigns({
      "GET /api/app/campaigns?kind=SMS": refusal(403, "This account cannot list campaigns"),
    });

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "This account cannot list campaigns",
    );
  });
});
