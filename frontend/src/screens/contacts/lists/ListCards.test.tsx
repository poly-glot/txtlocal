import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { refusal } from "@/test/fakeFetch";

import { renderContacts } from "../testing";

async function openMenu(user: ReturnType<typeof userEvent.setup>, name: string): Promise<void> {
  await screen.findByText("Example List");
  await user.click(screen.getByRole("button", { name: `Actions for ${name}` }));
}

describe("ListCards", () => {
  it("marks the first list as the open one", async () => {
    renderContacts();

    const row = await screen.findByRole("button", { name: /^Example List/u });

    expect(row).toHaveAttribute("aria-current", "true");
  });

  it("marks the opt-out list as the system list", async () => {
    renderContacts();

    const row = await screen.findByRole("button", { name: /^Opt-Out List/u });

    expect(row).toHaveTextContent("Opt-out");
  });

  it("offers Rename, Export and Delete on a standard list", async () => {
    const user = userEvent.setup();
    renderContacts();

    await openMenu(user, "Example List");

    expect(screen.getByRole("button", { name: "Rename" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Export" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Delete" })).toBeInTheDocument();
  });

  it("offers Export alone on the opt-out list", async () => {
    const user = userEvent.setup();
    renderContacts();

    await openMenu(user, "Opt-Out List");

    expect(screen.getByRole("button", { name: "Export" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Rename" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Delete" })).not.toBeInTheDocument();
  });

  it("deletes a list", async () => {
    const user = userEvent.setup();
    const fetcher = renderContacts({
      "DELETE /api/app/lists/list-example": new Response(null, { status: 204 }),
    });

    await openMenu(user, "Example List");
    await user.click(screen.getByRole("button", { name: "Delete" }));

    const call = fetcher.calls.find((one) => one.method === "DELETE");
    expect(call?.path).toBe("/api/app/lists/list-example");
  });

  it("renders the server's refusal of a delete verbatim", async () => {
    const user = userEvent.setup();
    renderContacts({
      "DELETE /api/app/lists/list-example": refusal(409, "The opt-out list cannot be deleted"),
    });

    await openMenu(user, "Example List");
    await user.click(screen.getByRole("button", { name: "Delete" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "The opt-out list cannot be deleted",
    );
  });

  it("exports a list as CSV", async () => {
    const user = userEvent.setup();
    const fetcher = renderContacts({
      "GET /api/app/lists/list-example/export": new Response("mobile\n+447400123123\n", {
        headers: { "content-type": "text/csv" },
        status: 200,
      }),
    });

    await openMenu(user, "Example List");
    await user.click(screen.getByRole("button", { name: "Export" }));

    const call = fetcher.calls.find((one) => one.path.endsWith("/export"));
    expect(call?.path).toBe("/api/app/lists/list-example/export");
  });
});
