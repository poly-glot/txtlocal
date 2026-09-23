import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { refusal } from "@/test/fakeFetch";
import { NEW_API_KEY } from "@/test/fixtures/identity";

import { addSubaccount, renderSubaccounts } from "./testing";

describe("SubaccountsTab", () => {
  it("lists every user with the start of its key", async () => {
    renderSubaccounts();

    expect(await screen.findByText("k7Qx2m9P…")).toBeInTheDocument();
    expect(screen.getByText("aB3dE5fG…")).toBeInTheDocument();
    expect(screen.getByText("Support desk")).toBeInTheDocument();
    expect(screen.getByText("Owner")).toBeInTheDocument();
  });

  it("adds a subaccount and shows the key once", async () => {
    const user = userEvent.setup();
    const fetcher = renderSubaccounts();

    await addSubaccount(user);

    const dialog = await screen.findByRole("dialog", { name: "Your new API key" });
    expect(within(dialog).getByLabelText("API key")).toHaveValue(NEW_API_KEY);
    expect(
      within(dialog).getByText("Store this key now. For your security we cannot show it again."),
    ).toBeInTheDocument();
    const post = fetcher.calls.find((call) => call.method === "POST");
    expect(post?.body).toEqual({ firstName: "Sam", lastName: "", username: "new@txtlocal.local" });
  });

  it("renders the server's refusal verbatim", async () => {
    const user = userEvent.setup();
    renderSubaccounts({
      "POST /api/app/account/users": refusal(409, "That email address already has an account"),
    });

    await addSubaccount(user);

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "That email address already has an account",
    );
  });

  it("sorts by the clicked header", async () => {
    const user = userEvent.setup();
    renderSubaccounts();
    await screen.findByText("k7Qx2m9P…");

    await user.click(screen.getByRole("button", { name: "USERNAME" }));

    const [, firstRow] = screen.getAllByRole("row");
    expect(firstRow).toHaveTextContent("sub@txtlocal.local");
  });

  it("searches on submit and shows the empty sentence", async () => {
    const user = userEvent.setup();
    renderSubaccounts({ "GET /api/app/account/users?q=zzz": [] });

    await user.type(await screen.findByLabelText("Search"), "zzz{Enter}");

    expect(await screen.findByText("No subaccounts match your search.")).toBeInTheDocument();
  });

  it("keeps the search text once the results arrive", async () => {
    const user = userEvent.setup();
    renderSubaccounts({ "GET /api/app/account/users?q=zzz": [] });

    await user.type(await screen.findByLabelText("Search"), "zzz{Enter}");
    await screen.findByText("No subaccounts match your search.");

    expect(screen.getByLabelText("Search")).toHaveValue("zzz");
  });
});
