import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { field, refusal } from "@/test/fakeFetch";
import { EXAMPLE_LIST, OPT_OUT_LIST } from "@/test/fixtures/contacts";

import { renderContacts } from "./testing";

describe("ContactsScreen", () => {
  it("shows every list with its contact count", async () => {
    renderContacts();
    const lists = await screen.findByRole("list", { name: "Lists" });

    expect(within(lists).getByText("Example List")).toBeInTheDocument();
    expect(within(lists).getByText("2 contacts")).toBeInTheDocument();
    expect(within(lists).getByText("Opt-Out List")).toBeInTheDocument();
    expect(within(lists).getByText("0 contacts")).toBeInTheDocument();
  });

  it("opens the first list on the right", async () => {
    renderContacts();

    expect(await screen.findByRole("heading", { level: 2, name: "Example List" })).toBeVisible();
    expect(await screen.findByText("sam@example.com")).toBeInTheDocument();
  });

  it("opens another list when its card is chosen", async () => {
    const user = userEvent.setup();
    renderContacts();

    await user.click(await screen.findByRole("button", { name: /^Opt-Out List/u }));

    expect(await screen.findByRole("heading", { level: 2, name: "Opt-Out List" })).toBeVisible();
  });

  it("clears the selection when another list opens", async () => {
    const user = userEvent.setup();
    renderContacts();
    await screen.findByText("sam@example.com");
    await user.click(screen.getByRole("checkbox", { name: "Select +447400123123" }));
    await screen.findByText("1 selected");

    await user.click(screen.getByRole("button", { name: /^Opt-Out List/u }));

    await screen.findByRole("heading", { level: 2, name: "Opt-Out List" });
    expect(screen.queryByText("1 selected")).not.toBeInTheDocument();
  });

  it("searches the lists on the server", async () => {
    const user = userEvent.setup();
    const fetcher = renderContacts({ "GET /api/app/lists?q=Opt": [OPT_OUT_LIST] });
    await screen.findByText("Example List");

    await user.type(screen.getByLabelText("Search lists"), "Opt{Enter}");

    await screen.findByRole("heading", { level: 2, name: "Opt-Out List" });
    expect(fetcher.calls.some((call) => call.path === "/api/app/lists?q=Opt")).toBe(true);
  });

  it("keeps the search text while the filtered lists load", async () => {
    const user = userEvent.setup();
    renderContacts({ "GET /api/app/lists?q=Opt": [OPT_OUT_LIST] });
    await screen.findByText("Example List");

    await user.type(screen.getByLabelText("Search lists"), "Opt{Enter}");

    await screen.findByRole("heading", { level: 2, name: "Opt-Out List" });
    expect(screen.getByLabelText("Search lists")).toHaveValue("Opt");
  });

  it("says when no list matches the search", async () => {
    const user = userEvent.setup();
    renderContacts({ "GET /api/app/lists?q=none": [] });
    await screen.findByText("Example List");

    await user.type(screen.getByLabelText("Search lists"), "none{Enter}");

    expect(await screen.findByText("No lists found.")).toBeInTheDocument();
  });

  it("offers import only when a list is open", async () => {
    const user = userEvent.setup();
    renderContacts({ "GET /api/app/lists?q=none": [] });
    await screen.findByText("Example List");
    await user.type(screen.getByLabelText("Search lists"), "none{Enter}");
    await screen.findByText("No lists found.");

    await user.click(screen.getByRole("button", { name: "New list or import contacts" }));

    expect(screen.getByRole("button", { name: "New list" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Import contacts" })).not.toBeInTheDocument();
  });

  it("creates a list", async () => {
    const user = userEvent.setup();
    const created = { ...EXAMPLE_LIST, contactCount: 0, listId: "list-leads", name: "Leads" };
    const fetcher = renderContacts({ "POST /api/app/lists": created });
    await screen.findByText("Example List");

    await user.click(screen.getByRole("button", { name: "New list or import contacts" }));
    await user.click(screen.getByRole("button", { name: "New list" }));
    await user.type(screen.getByLabelText("Name"), "Leads");
    await user.click(screen.getByRole("button", { name: "ADD" }));

    const call = fetcher.calls.find((one) => one.method === "POST");
    expect(call?.path).toBe("/api/app/lists");
    expect(field(call, "name")).toBe("Leads");
  });

  it("renames a list", async () => {
    const user = userEvent.setup();
    const renamed = { ...EXAMPLE_LIST, name: "Customers" };
    const fetcher = renderContacts({ "PATCH /api/app/lists/list-example": renamed });
    await screen.findByText("Example List");

    await user.click(screen.getByRole("button", { name: "Actions for Example List" }));
    await user.click(screen.getByRole("button", { name: "Rename" }));
    await user.clear(screen.getByLabelText("Name"));
    await user.type(screen.getByLabelText("Name"), "Customers");
    await user.click(screen.getByRole("button", { name: "SAVE" }));

    const call = fetcher.calls.find((one) => one.method === "PATCH");
    expect(field(call, "name")).toBe("Customers");
  });

  it("renders the server's refusal of a rename verbatim", async () => {
    const user = userEvent.setup();
    renderContacts({
      "PATCH /api/app/lists/list-example": refusal(409, "You already have a list with that name"),
    });
    await screen.findByText("Example List");

    await user.click(screen.getByRole("button", { name: "Actions for Example List" }));
    await user.click(screen.getByRole("button", { name: "Rename" }));
    await user.click(screen.getByRole("button", { name: "SAVE" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "You already have a list with that name",
    );
  });
});
