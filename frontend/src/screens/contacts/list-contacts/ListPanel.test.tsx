import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { field, refusal } from "@/test/fakeFetch";
import { ALEX, CONTACTS_PATH, SAM } from "@/test/fixtures/contacts";

import { renderContacts } from "../testing";

const HEADERS = [
  "DATE UPDATED",
  "FIRST NAME",
  "LAST NAME",
  "MOBILE",
  "EMAIL",
  "(CF1)",
  "(CF2)",
  "(CF3)",
  "(CF4)",
];

describe("ListPanel", () => {
  it("heads the table with the nine columns", async () => {
    renderContacts();
    await screen.findByText("sam@example.com");

    for (const header of HEADERS) {
      expect(screen.getByRole("columnheader", { name: header })).toBeInTheDocument();
    }
  });

  it("shows the date updated in the account's time zone", async () => {
    renderContacts();

    expect(await screen.findByText("19/09/2026, 13:00")).toBeInTheDocument();
  });

  it("says when the list holds no contacts", async () => {
    renderContacts({ [`GET ${CONTACTS_PATH}?limit=20`]: { cursor: null, items: [] } });

    expect(await screen.findByText("No contacts in this list yet.")).toBeInTheDocument();
  });

  it("sorts the rows by first name", async () => {
    const user = userEvent.setup();
    renderContacts();
    await screen.findByText("sam@example.com");

    await user.click(screen.getByRole("button", { name: "FIRST NAME" }));

    const [, first] = screen.getAllByRole("row");
    expect(within(first ?? document.body).getByText("Alex")).toBeInTheDocument();
  });

  it("adds a contact", async () => {
    const user = userEvent.setup();
    const fetcher = renderContacts({ [`POST ${CONTACTS_PATH}`]: SAM });
    await screen.findByText("sam@example.com");

    await user.click(screen.getByRole("button", { name: "Add contact" }));
    await user.type(screen.getByLabelText("First Name"), "Kim");
    await user.type(screen.getByLabelText("Mobile"), "07400123123");
    await user.click(screen.getByRole("button", { name: "ADD" }));

    const call = fetcher.calls.find((one) => one.method === "POST");
    expect(call?.path).toBe(CONTACTS_PATH);
    expect(field(call, "firstName")).toBe("Kim");
    expect(field(call, "mobile")).toBe("07400123123");
  });

  it("edits the contact behind its mobile", async () => {
    const user = userEvent.setup();
    const fetcher = renderContacts({
      [`PATCH ${CONTACTS_PATH}/%2B447400123123`]: { ...SAM, lastName: "Rae" },
    });
    await screen.findByText("sam@example.com");

    await user.click(screen.getByRole("button", { name: "Edit +447400123123" }));
    await user.clear(screen.getByLabelText("Last Name"));
    await user.type(screen.getByLabelText("Last Name"), "Rae");
    await user.click(screen.getByRole("button", { name: "SAVE" }));

    const call = fetcher.calls.find((one) => one.method === "PATCH");
    expect(call?.path).toBe(`${CONTACTS_PATH}/%2B447400123123`);
    expect(field(call, "lastName")).toBe("Rae");
  });

  it("deletes the selected contacts and reports the server's count", async () => {
    const user = userEvent.setup();
    const fetcher = renderContacts({
      [`POST ${CONTACTS_PATH}/bulk`]: { message: "Removed 2 contacts", removed: 2 },
    });
    await screen.findByText("sam@example.com");

    await user.click(screen.getByRole("checkbox", { name: "Select all contacts" }));
    await user.click(screen.getByRole("button", { name: "Delete" }));

    expect(await screen.findByText("Removed 2 contacts")).toBeInTheDocument();
    const call = fetcher.calls.find((one) => one.path.endsWith("/bulk"));
    expect(field(call, "action")).toBe("DELETE");
    expect(field(call, "contactIds")).toEqual(["+447400123123", "+447400999888"]);
  });

  it("moves the selected contacts to the opt-out list", async () => {
    const user = userEvent.setup();
    const fetcher = renderContacts({
      [`POST ${CONTACTS_PATH}/bulk`]: {
        message: "Moved 1 contact to the opt-out list",
        removed: 1,
      },
    });
    await screen.findByText("sam@example.com");

    await user.click(screen.getByRole("checkbox", { name: "Select +447400123123" }));
    await user.click(screen.getByRole("button", { name: "Move to opt-out" }));

    expect(await screen.findByText("Moved 1 contact to the opt-out list")).toBeInTheDocument();
    const call = fetcher.calls.find((one) => one.path.endsWith("/bulk"));
    expect(field(call, "action")).toBe("OPT_OUT");
  });

  it("removes the invalid numbers of a list", async () => {
    const user = userEvent.setup();
    const fetcher = renderContacts({
      "POST /api/app/lists/list-example/clean-up": { message: "Removed 3 contacts", removed: 3 },
    });
    await screen.findByText("sam@example.com");

    await user.click(screen.getByRole("button", { name: "Clean Up" }));
    await user.click(screen.getByRole("button", { name: "Remove invalid numbers" }));

    expect(await screen.findByText("Removed 3 contacts")).toBeInTheDocument();
    const call = fetcher.calls.find((one) => one.path.endsWith("/clean-up"));
    expect(field(call, "action")).toBe("INVALID");
  });

  it("removes the opted-out contacts of a list", async () => {
    const user = userEvent.setup();
    const fetcher = renderContacts({
      "POST /api/app/lists/list-example/clean-up": { message: "Removed 1 contact", removed: 1 },
    });
    await screen.findByText("sam@example.com");

    await user.click(screen.getByRole("button", { name: "Clean Up" }));
    await user.click(screen.getByRole("button", { name: "Remove opted-out contacts" }));

    const call = fetcher.calls.find((one) => one.path.endsWith("/clean-up"));
    expect(field(call, "action")).toBe("OPTED_OUT");
  });

  it("renders the server's refusal of a clean-up verbatim", async () => {
    const user = userEvent.setup();
    renderContacts({
      "POST /api/app/lists/list-example/clean-up": refusal(
        409,
        "The opt-out list cannot be cleaned up",
      ),
    });
    await screen.findByText("sam@example.com");

    await user.click(screen.getByRole("button", { name: "Clean Up" }));
    await user.click(screen.getByRole("button", { name: "Remove invalid numbers" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "The opt-out list cannot be cleaned up",
    );
  });

  it("sends Send to All to Quick SMS with the list", async () => {
    renderContacts();

    expect(await screen.findByRole("link", { name: "Send to All" })).toHaveAttribute(
      "href",
      "/sms/quick?listId=list-example",
    );
  });

  it("sends Group SMS to Quick SMS with the list", async () => {
    renderContacts();

    expect(await screen.findByRole("link", { name: "Group SMS" })).toHaveAttribute(
      "href",
      "/sms/quick?listId=list-example",
    );
  });

  it("searches the contacts of the list on the server", async () => {
    const user = userEvent.setup();
    const fetcher = renderContacts({
      [`GET ${CONTACTS_PATH}?limit=20&q=Sam`]: { cursor: null, items: [SAM] },
    });
    await screen.findByText("sam@example.com");

    await user.type(screen.getByLabelText("Search contacts"), "Sam{Enter}");

    await screen.findByText("sam@example.com");
    expect(fetcher.calls.some((one) => one.path === `${CONTACTS_PATH}?limit=20&q=Sam`)).toBe(true);
  });

  it("keeps the search text while the filtered contacts load", async () => {
    const user = userEvent.setup();
    renderContacts({
      [`GET ${CONTACTS_PATH}?limit=20&q=Sam`]: { cursor: null, items: [SAM] },
    });
    await screen.findByText("sam@example.com");

    await user.type(screen.getByLabelText("Search contacts"), "Sam{Enter}");

    await screen.findByText("sam@example.com");
    expect(screen.getByLabelText("Search contacts")).toHaveValue("Sam");
  });

  it("asks for more entries a page", async () => {
    const user = userEvent.setup();
    const fetcher = renderContacts({
      [`GET ${CONTACTS_PATH}?limit=50`]: { cursor: null, items: [SAM] },
    });
    await screen.findByText("sam@example.com");

    await user.selectOptions(screen.getByLabelText("Show Entries"), "50");

    expect(
      await screen.findByText("sam@example.com", undefined, { timeout: 2000 }),
    ).toBeInTheDocument();
    expect(fetcher.calls.some((one) => one.path === `${CONTACTS_PATH}?limit=50`)).toBe(true);
  });

  it("offers no next page when the list has no more contacts", async () => {
    renderContacts();
    await screen.findByText("sam@example.com");

    expect(screen.getByRole("button", { name: "Next" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Previous" })).toBeDisabled();
  });

  it("pages forward with the cursor the list answered", async () => {
    const user = userEvent.setup();
    renderContacts(pagedRoutes());
    await screen.findByText("sam@example.com");

    await user.click(screen.getByRole("button", { name: "Next" }));

    expect(await screen.findByText("alex@example.com")).toBeInTheDocument();
    expect(screen.queryByText("sam@example.com")).not.toBeInTheDocument();
  });

  it("pages back to the first page", async () => {
    const user = userEvent.setup();
    renderContacts(pagedRoutes());
    await screen.findByText("sam@example.com");
    await user.click(screen.getByRole("button", { name: "Next" }));
    await screen.findByText("alex@example.com");

    await user.click(screen.getByRole("button", { name: "Previous" }));

    expect(await screen.findByText("sam@example.com")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Previous" })).toBeDisabled();
  });
});

function pagedRoutes(): Record<string, unknown> {
  return {
    [`GET ${CONTACTS_PATH}?limit=20`]: { cursor: "page-2", items: [SAM] },
    [`GET ${CONTACTS_PATH}?cursor=page-2&limit=20`]: { cursor: null, items: [ALEX] },
  };
}
