import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { refusal } from "@/test/fakeFetch";

import { PREVIEW_PLACEHOLDER, renderHome } from "./testing";

async function checklistStep(title: string): Promise<HTMLElement> {
  await screen.findByText(title);
  const step = screen.getAllByRole("listitem").find((item) => item.textContent.includes(title));
  if (step === undefined) {
    throw new Error(`No checklist step named ${title}`);
  }

  return step;
}

describe("HomeScreen", () => {
  it("welcomes the user by name", async () => {
    renderHome();

    expect(
      await screen.findByRole("heading", { level: 2, name: "Welcome to txtlocal Demo Owner!" }),
    ).toBeInTheDocument();
  });

  it("tells the user how many trial days are left", async () => {
    renderHome();

    expect(
      await screen.findByText(
        "Send some test messages with your free trial credit. You've got 12 days to try it out.",
      ),
    ).toBeInTheDocument();
  });

  it("shows the dashboard video with its length", async () => {
    renderHome();

    expect(await screen.findByText("Learn to use your Dashboard")).toBeInTheDocument();
    expect(screen.getByText("2 Mins")).toBeInTheDocument();
  });

  it("previews the placeholder while the message is empty", async () => {
    renderHome();
    const preview = await screen.findByRole("region", { name: "Message preview" });

    expect(within(preview).getByText(PREVIEW_PLACEHOLDER)).toBeInTheDocument();
    expect(within(preview).getByText("Preview on a handset")).toBeInTheDocument();
  });

  it("mirrors the typed message in the preview", async () => {
    const user = userEvent.setup();
    renderHome();
    const preview = await screen.findByRole("region", { name: "Message preview" });

    await user.type(screen.getByLabelText("Message content"), "Hello there");

    expect(within(preview).getByText("Hello there")).toBeInTheDocument();
    expect(within(preview).queryByText(PREVIEW_PLACEHOLDER)).not.toBeInTheDocument();
  });

  it("introduces the setup checklist", async () => {
    renderHome();

    expect(
      await screen.findByRole("heading", { level: 2, name: "Finish setting up your profile" }),
    ).toBeInTheDocument();
    expect(screen.getByText("A few quick steps and you're ready to send.")).toBeInTheDocument();
  });

  it("marks a verified step done with its note", async () => {
    renderHome();
    const step = await checklistStep("Verify your email");

    expect(within(step).getByRole("img", { name: "Done" })).toBeInTheDocument();
    expect(
      within(step).getByText("Email verified. Your account is good to go."),
    ).toBeInTheDocument();
  });

  it("marks an unverified step to do without a note", async () => {
    renderHome();
    const step = await checklistStep("Verify your number");

    expect(within(step).getByRole("img", { name: "To do" })).toBeInTheDocument();
    expect(screen.queryByText("All done. Your number is verified.")).not.toBeInTheDocument();
  });

  it("links to the developer docs for users not sending from the dashboard", async () => {
    renderHome();

    expect(await screen.findByText("Not sending from the dashboard?")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Switch your view" })).toHaveAttribute(
      "href",
      "/developer/docs",
    );
  });

  it("shows the trial days left", async () => {
    renderHome();

    expect(await screen.findByRole("term")).toHaveTextContent("Trial Days Left");
    expect(screen.getByRole("definition")).toHaveTextContent("12");
  });

  it("links to adding credits", async () => {
    renderHome();

    expect(await screen.findByRole("link", { name: "Add Credits" })).toHaveAttribute(
      "href",
      "/billing/top-up",
    );
  });

  it("switches to the getting-started tab", async () => {
    const user = userEvent.setup();
    renderHome();
    await screen.findByText(PREVIEW_PLACEHOLDER);

    await user.click(screen.getByRole("tab", { name: "GET STARTED WITH TXTLOCAL" }));

    expect(
      screen.getByText("Add contacts, set up a sender and send your first campaign."),
    ).toBeInTheDocument();
  });

  it("says it is loading until the dashboard arrives", () => {
    renderHome();

    expect(screen.getByText("Loading…")).toBeInTheDocument();
  });

  it("renders the server's sentence when the dashboard cannot load", async () => {
    renderHome({ "GET /api/app/home": refusal(401, "Sign in to continue") });

    expect(await screen.findByRole("alert")).toHaveTextContent("Sign in to continue");
  });
});
