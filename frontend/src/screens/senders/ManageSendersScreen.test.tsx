import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { refusal } from "@/test/fakeFetch";

import { renderSenders } from "./testing";

describe("ManageSendersScreen", () => {
  it("offers the three ways to send from", async () => {
    renderSenders();

    expect(await screen.findByRole("tab", { name: "Smart Senders" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    expect(screen.getByRole("tab", { name: "My Numbers" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Alpha Tags" })).toBeInTheDocument();
  });

  it("renders the server's refusal of the overview verbatim", async () => {
    renderSenders({ "GET /api/app/senders": refusal(403, "This account cannot manage senders") });

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "This account cannot manage senders",
    );
  });
});
