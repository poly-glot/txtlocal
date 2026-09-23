import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { field, refusal } from "@/test/fakeFetch";
import type { Call, FakeFetch } from "@/test/fakeFetch";
import { CONTACTS_PATH } from "@/test/fixtures/contacts";

import { renderContacts } from "../testing";

const HEADER_LINE = "mobile,first_name,last_name,email,cf1,cf2,cf3,cf4";

const numberedRow = (index: number) => `+4474001${String(index).padStart(5, "0")},Kim,Lee,,,,,`;

const csvOf = (rows: number) =>
  [HEADER_LINE, ...Array.from({ length: rows }, (_, index) => numberedRow(index))].join("\n");

const rowsOf = (call: Call | undefined): unknown[] => {
  const rows = field(call, "rows");

  return Array.isArray(rows) ? rows : [];
};

async function openImport(
  user: ReturnType<typeof userEvent.setup>,
  routes: Record<string, unknown> = {},
): Promise<FakeFetch> {
  const fetcher = renderContacts(routes);
  await screen.findByText("Example List");
  await user.click(screen.getByRole("button", { name: "New list or import contacts" }));
  await user.click(screen.getByRole("button", { name: "Import contacts" }));

  return fetcher;
}

async function upload(user: ReturnType<typeof userEvent.setup>, csv: string): Promise<void> {
  const file = new File([csv], "contacts.csv", { type: "text/csv" });
  await user.upload(screen.getByLabelText("CSV file"), file);
  await user.click(screen.getByRole("button", { name: "IMPORT" }));
}

describe("ImportModal", () => {
  it("reports what the server imported, updated and skipped", async () => {
    const user = userEvent.setup();
    await openImport(user, {
      [`POST ${CONTACTS_PATH}/import`]: {
        imported: 1,
        message: "Imported 1, updated 1, skipped 1 invalid",
        skipped: 1,
        updated: 1,
      },
    });

    await upload(user, csvOf(3));

    expect(await screen.findByText("Imported 1, updated 1, skipped 1 invalid")).toBeInTheDocument();
  });

  it("uploads the rows in chunks of 500 and sums the reports", async () => {
    const user = userEvent.setup();
    const fetcher = await openImport(user, {
      [`POST ${CONTACTS_PATH}/import`]: {
        imported: 1,
        message: "Imported 1, updated 0, skipped 0 invalid",
        skipped: 0,
        updated: 0,
      },
    });

    await upload(user, csvOf(501));

    expect(await screen.findByText("Imported 2, updated 0, skipped 0 invalid")).toBeInTheDocument();
    const calls = fetcher.calls.filter((one) => one.path.endsWith("/import"));
    expect(calls.map((one) => rowsOf(one).length)).toEqual([500, 1]);
  });

  it("refuses a CSV without a mobile column", async () => {
    const user = userEvent.setup();
    await openImport(user);

    await upload(user, "first_name\nKim");

    expect(await screen.findByRole("alert")).toHaveTextContent("The CSV needs a mobile column");
  });

  it("renders the server's refusal of an import verbatim", async () => {
    const user = userEvent.setup();
    await openImport(user, {
      [`POST ${CONTACTS_PATH}/import`]: refusal(400, "A list holds up to 10,000 contacts"),
    });

    await upload(user, csvOf(1));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "A list holds up to 10,000 contacts",
    );
  });
});
