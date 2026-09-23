import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { refusal } from "@/test/fakeFetch";

import { renderApiDocsScreen } from "./testing";

describe("ApiDocsScreen", () => {
  it("shows the loading message before the spec resolves", () => {
    renderApiDocsScreen();

    expect(screen.getByText("Loading…")).toBeInTheDocument();
  });

  it("groups operations by their path segment and shows each summary", async () => {
    renderApiDocsScreen();

    expect(await screen.findByRole("heading", { level: 3, name: "Account" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 3, name: "Lists" })).toBeInTheDocument();
    expect(screen.getByText("Balance")).toBeInTheDocument();
    expect(screen.getByText("Create List")).toBeInTheDocument();
  });

  it("shows a resolved response schema's fields", async () => {
    renderApiDocsScreen();

    expect(await screen.findByText("balance")).toBeInTheDocument();
    expect(screen.getByText("currency")).toBeInTheDocument();
  });

  it("shows a fixed message when the spec fails to load", async () => {
    renderApiDocsScreen({ "GET /openapi.v3.json": refusal(500, "unused") });

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Could not load the API reference. Try again.",
    );
  });
});
