import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { refusal } from "@/test/fakeFetch";
import { NEW_API_KEY } from "@/test/fixtures/identity";

import { addSubaccount, renderSubaccounts } from "./testing";

const REGENERATED = {
  apiKey: "R3gEn3r4t3dKeyValue0123456789abcdefghijk",
  apiKeyPrefix: "R3gEn3r4",
  userId: "user-1",
};
const QUESTION =
  "Regenerate the API key for demo@txtlocal.local? Integrations using the current key will stop working.";

describe("ApiKeyModal", () => {
  it("copies the key to the clipboard", async () => {
    const user = userEvent.setup();
    renderSubaccounts();
    await addSubaccount(user);
    const dialog = await screen.findByRole("dialog", { name: "Your new API key" });

    await user.click(within(dialog).getByRole("button", { name: "Copy" }));

    expect(await navigator.clipboard.readText()).toBe(NEW_API_KEY);
    expect(await within(dialog).findByRole("button", { name: "Copied" })).toBeInTheDocument();
  });

  it("closes on Done", async () => {
    const user = userEvent.setup();
    renderSubaccounts();
    await addSubaccount(user);
    const dialog = await screen.findByRole("dialog", { name: "Your new API key" });

    await user.click(within(dialog).getByRole("button", { name: "Done" }));

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("shows a regenerated key after the owner confirms", async () => {
    const user = userEvent.setup();
    const fetcher = renderSubaccounts({
      "POST /api/app/account/users/user-1/api-key": REGENERATED,
    });

    await user.click(
      await screen.findByRole("button", { name: "Regenerate API key for demo@txtlocal.local" }),
    );
    expect(screen.getByText(QUESTION)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "REGENERATE" }));

    const dialog = await screen.findByRole("dialog", { name: "Your new API key" });
    expect(within(dialog).getByLabelText("API key")).toHaveValue(REGENERATED.apiKey);
    expect(
      fetcher.calls.some((call) => call.path === "/api/app/account/users/user-1/api-key"),
    ).toBe(true);
  });

  it("keeps the key when the owner cancels", async () => {
    const user = userEvent.setup();
    const fetcher = renderSubaccounts();

    await user.click(
      await screen.findByRole("button", { name: "Regenerate API key for demo@txtlocal.local" }),
    );
    await user.click(screen.getByRole("button", { name: "CANCEL" }));

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(fetcher.calls.filter((call) => call.method === "POST")).toEqual([]);
  });

  it("renders the server's refusal when regeneration fails", async () => {
    const user = userEvent.setup();
    renderSubaccounts({
      "POST /api/app/account/users/user-1/api-key": refusal(403, "Only the owner can do that"),
    });

    await user.click(
      await screen.findByRole("button", { name: "Regenerate API key for demo@txtlocal.local" }),
    );
    await user.click(screen.getByRole("button", { name: "REGENERATE" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Only the owner can do that");
  });
});
