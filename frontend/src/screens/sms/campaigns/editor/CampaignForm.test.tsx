import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { field, refusal } from "@/test/fakeFetch";

import { composeCampaign, openEditor, renderCampaigns } from "../testing";

const CUSTOM_FIELDS_NOTE = "Custom fields are calculated and final count shown on confirmation.";
const EMPTY_PAGE = { cursor: null, items: [] };
const PREVIEW_CAPTION =
  "Placeholders will be replaced for all contacts in a list. This is an example of the first contact.";

const newCampaign = (routes: Record<string, unknown> = {}) =>
  renderCampaigns({ "GET /api/app/campaigns?kind=SMS": EMPTY_PAGE, ...routes });

describe("CampaignForm", () => {
  it("opens the three steps with only the sender complete", async () => {
    const user = userEvent.setup();
    newCampaign();

    await openEditor(user);

    expect(
      within(screen.getByRole("region", { name: "To" })).getByText("Not complete"),
    ).toBeInTheDocument();
    expect(
      within(screen.getByRole("region", { name: "From" })).getByText("Complete"),
    ).toBeInTheDocument();
    expect(
      within(screen.getByRole("region", { name: "Message" })).getByText("Not complete"),
    ).toBeInTheDocument();
  });

  it("names the step the campaign sends to", async () => {
    const user = userEvent.setup();
    newCampaign();

    await openEditor(user);

    expect(screen.getByRole("heading", { name: "To" })).toBeInTheDocument();
    expect(screen.getByText("Your Recipients")).toBeInTheDocument();
    expect(screen.getByLabelText("List")).toHaveDisplayValue("Select List");
  });

  it("summarises a chosen list and marks the step complete", async () => {
    const user = userEvent.setup();
    newCampaign();

    await openEditor(user);
    await user.selectOptions(screen.getByLabelText("List"), "list-example");

    expect(screen.getByText("Example List 2 recipient(s)")).toBeInTheDocument();
    expect(
      within(screen.getByRole("region", { name: "To" })).getByText("Complete"),
    ).toBeInTheDocument();
  });

  it("keeps the opt-out list out of the choices", async () => {
    const user = userEvent.setup();
    newCampaign();

    await openEditor(user);

    expect(
      within(screen.getByLabelText("List")).queryByRole("option", { name: "Opt-Out List" }),
    ).not.toBeInTheDocument();
  });

  it("counts characters and parts while the body is typed", async () => {
    const user = userEvent.setup();
    newCampaign();

    await openEditor(user);
    await user.type(screen.getByLabelText("Your SMS Content"), "Hello");

    expect(screen.getByText("Approx. 27 characters/1 SMS per recipient.")).toBeInTheDocument();
  });

  it("warns that custom fields are counted on confirmation", async () => {
    const user = userEvent.setup();
    newCampaign();

    await openEditor(user);

    expect(screen.getByText(CUSTOM_FIELDS_NOTE)).toBeInTheDocument();
  });

  it("explains how placeholders fill the preview", async () => {
    const user = userEvent.setup();
    newCampaign();

    await openEditor(user);

    expect(screen.getByText(PREVIEW_CAPTION)).toBeInTheDocument();
  });

  it("previews the message with its opt-out footer", async () => {
    const user = userEvent.setup();
    newCampaign();

    await openEditor(user);
    await user.type(screen.getByLabelText("Your SMS Content"), "Hello");
    const preview = screen.getByRole("region", { name: "Message preview" });

    expect(within(preview).getByText("Hello")).toBeInTheDocument();
    expect(within(preview).getByText("Reply STOP to opt-out")).toBeInTheDocument();
  });

  it("starts on Reply STOP with the stop footer", async () => {
    const user = userEvent.setup();
    newCampaign();

    await openEditor(user);

    expect(screen.getByRole("radio", { name: "Reply STOP" })).toBeChecked();
    expect(screen.getByLabelText("Footer")).toHaveValue("Reply STOP to opt-out");
  });

  it("swaps the footer when the unsubscribe link is chosen", async () => {
    const user = userEvent.setup();
    newCampaign();

    await openEditor(user);
    await user.click(screen.getByRole("radio", { name: "Unsubscribe Link" }));

    expect(screen.getByLabelText("Footer")).toHaveValue("Unsubscribe: {unsubscribe_link}");
  });

  it("saves a draft and confirms it", async () => {
    const user = userEvent.setup();
    const fetcher = newCampaign();

    await openEditor(user);
    await user.type(screen.getByLabelText("Campaign name"), "Helloworld");
    await user.click(screen.getByRole("button", { name: "SAVE DRAFT" }));

    expect(await screen.findByText("Draft saved.")).toBeInTheDocument();
    const created = fetcher.calls.find(
      (call) => call.method === "POST" && call.path === "/api/app/campaigns",
    );
    expect(field(created, "name")).toBe("Helloworld");
  });

  it("keeps SEND NOW disabled before the campaign is priced", async () => {
    const user = userEvent.setup();
    newCampaign();

    await openEditor(user);

    expect(screen.getByRole("button", { name: "SEND NOW" })).toBeDisabled();
  });

  it("enables SEND NOW once NEXT has priced the campaign", async () => {
    const user = userEvent.setup();
    newCampaign();

    await composeCampaign(user);

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "SEND NOW" })).toBeEnabled();
    });
  });

  it("renders the server's refusal of NEXT verbatim", async () => {
    const user = userEvent.setup();
    newCampaign({
      "POST /api/app/campaigns/campaign-1/quote": refusal(
        400,
        "Select the list this campaign sends to",
      ),
    });

    await composeCampaign(user);

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Select the list this campaign sends to",
    );
  });

  it("confirms the send with the sender, the recipients, the date and the cost", async () => {
    const user = userEvent.setup();
    newCampaign();

    await composeCampaign(user);
    await user.click(await screen.findByRole("button", { name: "SEND NOW" }));

    const dialog = await screen.findByRole("dialog", { name: "Helloworld" });
    expect(within(dialog).getByText("From:")).toBeInTheDocument();
    expect(within(dialog).getByText("Shared Number")).toBeInTheDocument();
    expect(within(dialog).getByText("Total Recipients:")).toBeInTheDocument();
    expect(within(dialog).getByText("Date:")).toBeInTheDocument();
    expect(within(dialog).getByText("Now")).toBeInTheDocument();
    expect(within(dialog).getByText("£0.0854")).toBeInTheDocument();
  });

  it("sends a campaign now", async () => {
    const user = userEvent.setup();
    const fetcher = newCampaign();

    await composeCampaign(user);
    await user.click(await screen.findByRole("button", { name: "SEND NOW" }));
    await user.click(await screen.findByRole("button", { name: "SEND" }));

    const scheduled = fetcher.calls.find(
      (call) => call.path === "/api/app/campaigns/campaign-1/schedule",
    );
    expect(scheduled?.body).toEqual({ now: true });
  });

  it("schedules a campaign for a picked moment", async () => {
    const user = userEvent.setup();
    const fetcher = newCampaign();

    await composeCampaign(user);
    await user.click(await screen.findByRole("button", { name: "Schedule for later" }));
    await user.clear(screen.getByLabelText("Send at"));
    await user.type(screen.getByLabelText("Send at"), "2027-07-31T23:59");
    await user.click(await screen.findByRole("button", { name: "SCHEDULE" }));

    const scheduled = fetcher.calls.find(
      (call) => call.path === "/api/app/campaigns/campaign-1/schedule",
    );
    expect(field(scheduled, "now")).toBe(false);
  });

  it("renders the server's refusal of a schedule verbatim", async () => {
    const user = userEvent.setup();
    newCampaign({
      "POST /api/app/campaigns/campaign-1/schedule": refusal(
        400,
        "Schedule a campaign at least five minutes ahead",
      ),
    });

    await composeCampaign(user);
    await user.click(await screen.findByRole("button", { name: "SEND NOW" }));
    await user.click(await screen.findByRole("button", { name: "SEND" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Schedule a campaign at least five minutes ahead",
    );
  });

  it("asks to save when the editor is left with unsaved changes", async () => {
    const user = userEvent.setup();
    newCampaign();

    await openEditor(user);
    await user.type(screen.getByLabelText("Your SMS Content"), "Hello");
    await user.click(screen.getByRole("button", { name: "Back to campaigns" }));

    const dialog = await screen.findByRole("dialog", { name: "Save as a draft?" });
    expect(
      within(dialog).getByText("Come back to finalize and send your campaign later."),
    ).toBeInTheDocument();
    expect(within(dialog).getByRole("button", { name: "DISCARD DRAFT" })).toBeInTheDocument();
    expect(within(dialog).getByRole("button", { name: "SAVE DRAFT" })).toBeInTheDocument();
    expect(within(dialog).getByRole("button", { name: "Close" })).toBeInTheDocument();
  });

  it("leaves without asking when nothing was changed", async () => {
    const user = userEvent.setup();
    newCampaign();

    await openEditor(user);
    await user.click(screen.getByRole("button", { name: "Back to campaigns" }));

    expect(
      await screen.findByRole("button", { name: "CLICK HERE TO ADD YOUR FIRST SMS CAMPAIGN" }),
    ).toBeInTheDocument();
  });

  it("deletes the new campaign the draft dialog discards", async () => {
    const user = userEvent.setup();
    const fetcher = newCampaign();

    await composeCampaign(user);
    await user.type(screen.getByLabelText("Your SMS Content"), " again");
    await user.click(screen.getByRole("button", { name: "Back to campaigns" }));
    await user.click(await screen.findByRole("button", { name: "DISCARD DRAFT" }));

    expect(fetcher.calls.some((call) => call.method === "DELETE")).toBe(true);
  });

  it("moves focus to the name field from Edit name", async () => {
    const user = userEvent.setup();
    newCampaign();

    await openEditor(user);
    await user.click(screen.getByRole("button", { name: "Edit name" }));

    expect(screen.getByLabelText("Campaign name")).toHaveFocus();
  });
});

describe("CampaignForm on MMS", () => {
  const newMms = () => renderCampaigns({ "GET /api/app/campaigns?kind=MMS": EMPTY_PAGE }, "MMS");

  it("names the MMS content step", async () => {
    const user = userEvent.setup();
    newMms();

    await openEditor(user);

    expect(screen.getByLabelText("Your MMS Content")).toBeInTheDocument();
  });

  it("counts one MMS per recipient whatever the body", async () => {
    const user = userEvent.setup();
    newMms();

    await openEditor(user);
    await user.type(screen.getByLabelText("Your MMS Content"), "Hello");

    expect(screen.getByText("1 MMS per recipient.")).toBeInTheDocument();
  });

  it("names the sender step for MMS", async () => {
    const user = userEvent.setup();
    newMms();

    await openEditor(user);

    expect(screen.getByText("Your Sender Details")).toBeInTheDocument();
  });

  it("links to where replies go", async () => {
    const user = userEvent.setup();
    newMms();

    await openEditor(user);

    expect(
      screen.getByRole("link", { name: "Where do contacts' replies go?" }),
    ).toBeInTheDocument();
  });

  it("asks for a subject", async () => {
    const user = userEvent.setup();
    newMms();

    await openEditor(user);

    expect(screen.getByLabelText("Subject")).toBeInTheDocument();
  });
});
