import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { fakeFetch } from "@/test/fakeFetch";
import { ACCOUNT_SETTINGS } from "@/test/fixtures/identity";
import { renderWithProviders } from "@/test/render";

import { AccountSettingsScreen } from "./AccountSettingsScreen";

function renderSettings() {
  const fetcher = fakeFetch({
    "GET /api/app/account/settings": ACCOUNT_SETTINGS,
    "PUT /api/app/account/settings": {},
  });
  renderWithProviders(<AccountSettingsScreen />, { fetcher });

  return fetcher;
}

describe("AccountSettingsScreen", () => {
  it("loads the account name, time zone and default country", async () => {
    renderSettings();

    expect(await screen.findByLabelText("Account Name")).toHaveValue("Demo Ltd");
    expect(screen.getByLabelText("Timezone")).toHaveValue("Europe/London");
    expect(screen.getByLabelText("Default Country Code")).toHaveValue("GB");
  });

  it("saves every field and confirms", async () => {
    const user = userEvent.setup();
    const fetcher = renderSettings();
    const name = await screen.findByLabelText("Account Name");

    await user.clear(name);
    await user.type(name, "Acme Ltd");
    await user.selectOptions(screen.getByLabelText("Default Country Code"), "US");
    await user.click(screen.getByRole("button", { name: "Save" }));

    expect(await screen.findByText("Settings saved.")).toBeInTheDocument();
    const put = fetcher.calls.find((call) => call.method === "PUT");
    expect(put).toMatchObject({
      body: { defaultCountry: "US", name: "Acme Ltd", timezone: "Europe/London" },
      path: "/api/app/account/settings",
    });
  });
});
