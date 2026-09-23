import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { GENERAL } from "@/test/fixtures/developer";
import { refusal } from "@/test/fakeFetch";

import { renderApiGeneralTab } from "./testing";

describe("ApiGeneralTab", () => {
  it("shows the base URL, authentication, docs link and rate limit from the fixture", async () => {
    renderApiGeneralTab();

    expect(await screen.findByText(GENERAL.baseUrl)).toBeInTheDocument();
    expect(screen.getByText("HTTP Basic with your username and API key")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "API Documentation" })).toHaveAttribute(
      "href",
      "/developer/docs",
    );
    expect(screen.getByText("60 requests per minute per key")).toBeInTheDocument();
  });

  it("renders the server's refusal verbatim", async () => {
    renderApiGeneralTab({
      "GET /api/app/developer/general": refusal(500, "Something went wrong on our side"),
    });

    expect(await screen.findByRole("alert")).toHaveTextContent("Something went wrong on our side");
  });
});
