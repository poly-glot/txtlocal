import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { refusal } from "@/test/fakeFetch";
import { ALPHA_OVERVIEW } from "@/test/fixtures/senders";

import { openTab, renderSenders } from "../testing";

async function openAlphaTags(
  user: ReturnType<typeof userEvent.setup>,
  routes: Record<string, unknown> = {},
): Promise<void> {
  renderSenders(routes);
  await openTab(user, "Alpha Tags");
}

describe("AlphaTagsTab", () => {
  it("shows an empty area with no copy when there are no alpha tags", async () => {
    await openAlphaTags(userEvent.setup());

    expect(screen.getByRole("heading", { level: 2, name: "Alpha Tags" })).toBeInTheDocument();
    expect(
      screen.getByText("Create unique sender names to brand your messages."),
    ).toBeInTheDocument();
    expect(screen.queryByRole("row")).not.toBeInTheDocument();
  });

  it("lists a registered alpha tag with its use case and status", async () => {
    const user = userEvent.setup();
    renderSenders({ "GET /api/app/senders": ALPHA_OVERVIEW });

    await openTab(user, "Alpha Tags");

    const row = screen.getByText("TXTLOCAL").closest("tr");
    expect(row).not.toBeNull();
    expect(within(row as HTMLElement).getByText("Marketing")).toBeInTheDocument();
    expect(within(row as HTMLElement).getByText("Under review")).toBeInTheDocument();
  });

  it("opens the register modal from Add", async () => {
    const user = userEvent.setup();
    await openAlphaTags(user);

    await user.click(screen.getByRole("button", { name: "+ Add" }));

    expect(screen.getByRole("dialog", { name: "Register an alpha tag" })).toBeInTheDocument();
  });

  it("registers an alpha tag and closes the modal", async () => {
    const user = userEvent.setup();
    const fetcher = await registerAlphaTag(user);

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    const posted = fetcher.calls.find((call) => call.path === "/api/app/senders/alpha");
    expect(posted?.body).toEqual({ country: "GB", tag: "TXTLOCAL", useCase: "MARKETING" });
  });

  it("renders the server's refusal of registration verbatim", async () => {
    const user = userEvent.setup();
    await openAlphaTags(user, {
      "POST /api/app/senders/alpha": refusal(
        400,
        "Enter an alpha tag of 3 to 11 characters: letters, numbers and + only",
      ),
    });

    await user.click(screen.getByRole("button", { name: "+ Add" }));
    await user.type(screen.getByLabelText("Alpha Tag"), "TXTLOCAL");
    await user.click(screen.getByRole("button", { name: "Register Alpha Tag" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Enter an alpha tag of 3 to 11 characters: letters, numbers and + only",
    );
  });
});

async function registerAlphaTag(user: ReturnType<typeof userEvent.setup>) {
  const fetcher = renderSenders();
  await openTab(user, "Alpha Tags");
  await user.click(screen.getByRole("button", { name: "+ Add" }));
  await user.type(screen.getByLabelText("Alpha Tag"), "TXTLOCAL");
  await user.click(screen.getByRole("button", { name: "Register Alpha Tag" }));

  return fetcher;
}
