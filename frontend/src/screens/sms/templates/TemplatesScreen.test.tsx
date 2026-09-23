import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { renderTemplates } from "./testing";

const ADD_FIRST = "Click here to add your first SMS template";

describe("TemplatesScreen", () => {
  it("invites the first template when there are none", async () => {
    renderTemplates({ "GET /api/app/templates": [] });

    expect(await screen.findByRole("button", { name: ADD_FIRST })).toBeInTheDocument();
  });

  it("lists a template by name and body", async () => {
    renderTemplates();

    expect(await screen.findByText("Welcome")).toBeInTheDocument();
    expect(screen.getByText("Hello {first_name}")).toBeInTheDocument();
  });

  it("names the heading, the search and the two columns", async () => {
    renderTemplates();

    expect(await screen.findByLabelText("Search")).toHaveAttribute("placeholder", "Search...");
    expect(screen.getByRole("heading", { name: "SMS Templates" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Add template" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "NAME" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "BODY" })).toBeInTheDocument();
  });

  it("says there are no results when the search matches nothing", async () => {
    const user = userEvent.setup();
    renderTemplates();

    await user.type(await screen.findByLabelText("Search"), "nothing");

    expect(screen.getByText("No results")).toBeInTheDocument();
  });

  it("counts characters and parts while the body is typed", async () => {
    const user = userEvent.setup();
    renderTemplates({ "GET /api/app/templates": [] });

    await user.click(await screen.findByRole("button", { name: ADD_FIRST }));
    await user.type(screen.getByLabelText("Body"), "Hello");

    expect(screen.getByText("Approx. 5 characters/1 SMS per recipient.")).toBeInTheDocument();
  });

  it("keeps ADD disabled until the name and the body are filled", async () => {
    const user = userEvent.setup();
    renderTemplates({ "GET /api/app/templates": [] });

    await user.click(await screen.findByRole("button", { name: ADD_FIRST }));
    const add = screen.getByRole("button", { name: "ADD" });

    expect(add).toBeDisabled();
    await user.type(screen.getByLabelText("Template Name"), "Welcome");
    expect(add).toBeDisabled();
    await user.type(screen.getByLabelText("Body"), "Hello");

    expect(add).toBeEnabled();
  });

  it("saves a new template and confirms it", async () => {
    const user = userEvent.setup();
    const fetcher = renderTemplates({ "GET /api/app/templates": [] });

    await user.click(await screen.findByRole("button", { name: ADD_FIRST }));
    await user.type(screen.getByLabelText("Template Name"), "Welcome");
    await user.type(screen.getByLabelText("Body"), "Hello");
    await user.click(screen.getByRole("button", { name: "ADD" }));

    expect(await screen.findByText("New template has been saved.")).toBeInTheDocument();
    const created = fetcher.calls.find(
      (call) => call.method === "POST" && call.path === "/api/app/templates",
    );
    expect(created?.body).toEqual({ body: "Hello", name: "Welcome" });
  });

  it("edits a template in place", async () => {
    const user = userEvent.setup();
    const fetcher = renderTemplates({ "PUT /api/app/templates/template-1": {} });

    await user.click(await screen.findByRole("button", { name: "Edit Welcome" }));
    const dialog = screen.getByRole("dialog", { name: "SMS Template" });
    await user.clear(within(dialog).getByLabelText("Template Name"));
    await user.type(within(dialog).getByLabelText("Template Name"), "Welcome back");
    await user.click(within(dialog).getByRole("button", { name: "ADD" }));

    const saved = fetcher.calls.find((call) => call.method === "PUT");
    expect(saved?.body).toEqual({ body: "Hello {first_name}", name: "Welcome back" });
  });

  it("deletes a template", async () => {
    const user = userEvent.setup();
    const fetcher = renderTemplates({ "DELETE /api/app/templates/template-1": {} });

    await user.click(await screen.findByRole("button", { name: "Delete Welcome" }));

    expect(fetcher.calls.some((call) => call.method === "DELETE")).toBe(true);
  });

  it("renders the server's refusal verbatim", async () => {
    renderTemplates({
      "GET /api/app/templates": new Response(JSON.stringify({ message: "Template not found" }), {
        headers: { "content-type": "application/json" },
        status: 404,
      }),
    });

    expect(await screen.findByRole("alert")).toHaveTextContent("Template not found");
  });
});
