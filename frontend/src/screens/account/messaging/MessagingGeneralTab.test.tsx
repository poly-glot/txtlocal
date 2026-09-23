import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { fakeFetch } from "@/test/fakeFetch";
import { MESSAGING_SETTINGS } from "@/test/fixtures/identity";
import { renderWithProviders } from "@/test/render";

import { MessagingGeneralTab } from "./MessagingGeneralTab";

function renderSettings() {
  const fetcher = fakeFetch({
    "GET /api/app/account/settings/messaging": MESSAGING_SETTINGS,
    "PUT /api/app/account/settings/messaging": {},
  });
  renderWithProviders(<MessagingGeneralTab />, { fetcher });

  return fetcher;
}

const lastPut = (fetcher: ReturnType<typeof renderSettings>) =>
  fetcher.calls.find((call) => call.method === "PUT");

describe("MessagingGeneralTab", () => {
  it("offers one to eight message parts with their character counts", async () => {
    renderSettings();

    expect(await screen.findByRole("option", { name: "1 = 160 characters" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "8 = 1224 characters" })).toBeInTheDocument();
    expect(screen.getByLabelText("Max number of message parts:")).toHaveValue("8");
  });

  it("explains the unicode modes and the default country", async () => {
    renderSettings();

    expect(
      await screen.findByText(
        "Autodetect: Will allow normal GSM characters and unicode characters (e.g. English, French and Chinese Characters)",
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        "Force non-unicode: Will only allow GSM characters http://en.wikipedia.org/wiki/GSM_03.38",
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        "If the recipient phone number isn't formatted in international format, we'll automatically format it for you. This will use the country below.",
      ),
    ).toBeInTheDocument();
  });

  it("saves the from options from their own section", async () => {
    const user = userEvent.setup();
    const fetcher = renderSettings();
    const own = await screen.findByLabelText("Show the 'Your Number' option on the dashboard:");

    await user.selectOptions(own, "No");
    await user.click(
      within(screen.getByRole("form", { name: "From Options" })).getByRole("button", {
        name: "Save",
      }),
    );

    expect(await screen.findByText("Settings saved.")).toBeInTheDocument();
    expect(lastPut(fetcher)?.body).toEqual({ ...MESSAGING_SETTINGS, showOwnNumber: false });
  });

  it("saves the unicode choice from its own section", async () => {
    const user = userEvent.setup();
    const fetcher = renderSettings();

    await user.click(await screen.findByLabelText("Force non unicode (GSM Characters only)"));
    await user.click(
      within(screen.getByRole("form", { name: "Unicode" })).getByRole("button", { name: "Save" }),
    );

    expect(await screen.findByText("Settings saved.")).toBeInTheDocument();
    expect(lastPut(fetcher)?.body).toEqual({ ...MESSAGING_SETTINGS, unicodeMode: "GSM_ONLY" });
  });

  it("saves the character limit from its own section", async () => {
    const user = userEvent.setup();
    const fetcher = renderSettings();

    await user.selectOptions(await screen.findByLabelText("Max number of message parts:"), "4");
    await user.click(
      within(screen.getByRole("form", { name: "Character Limit" })).getByRole("button", {
        name: "Save",
      }),
    );

    expect(await screen.findByText("Settings saved.")).toBeInTheDocument();
    expect(lastPut(fetcher)?.body).toEqual({ ...MESSAGING_SETTINGS, maxParts: 4 });
  });
});
