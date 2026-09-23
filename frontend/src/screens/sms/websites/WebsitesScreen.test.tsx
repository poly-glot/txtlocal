import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { refusal } from "@/test/fakeFetch";

import { renderWebsites } from "./testing";

describe("WebsitesScreen", () => {
  it("registers a website end to end", async () => {
    const user = userEvent.setup();
    const fetcher = renderWebsites({
      "GET /api/app/websites": [],
      "POST /api/app/websites": [
        { domain: "junaid.guru", registeredAt: "2026-09-19T10:00:00Z", status: "UNDER_REVIEW" },
      ],
    });

    await user.click(await screen.findByRole("button", { name: "Register a website" }));
    await user.type(screen.getByLabelText("Website Domain"), "junaid.guru");
    await user.click(screen.getByRole("button", { name: "Register" }));

    const created = fetcher.calls.find((call) => call.method === "POST");
    expect(created?.body).toEqual({ domains: ["junaid.guru"] });
  });

  it("stops adding rows at three websites", async () => {
    const user = userEvent.setup();
    renderWebsites({ "GET /api/app/websites": [] });

    await user.click(await screen.findByRole("button", { name: "Register a website" }));
    expect(screen.getAllByLabelText("Website Domain")).toHaveLength(1);

    await user.click(screen.getByRole("button", { name: "Add another website +" }));
    expect(screen.getAllByLabelText("Website Domain")).toHaveLength(2);

    await user.click(screen.getByRole("button", { name: "Add another website +" }));
    expect(screen.getAllByLabelText("Website Domain")).toHaveLength(3);
    expect(screen.queryByRole("button", { name: "Add another website +" })).not.toBeInTheDocument();
  });

  it("renders the server's refusal of a duplicate website verbatim", async () => {
    const user = userEvent.setup();
    renderWebsites({ "POST /api/app/websites": refusal(409, "junaid.guru is already registered") });

    await user.click(await screen.findByRole("button", { name: "+ Register a website" }));
    await user.type(screen.getByLabelText("Website Domain"), "junaid.guru");
    await user.click(screen.getByRole("button", { name: "Register" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("junaid.guru is already registered");
  });

  it("shows a rejected website's reason", async () => {
    renderWebsites({
      "GET /api/app/websites": [
        {
          domain: "junaid.guru",
          registeredAt: "2026-09-19T10:00:00Z",
          rejectedReason: "Looks like a phishing page",
          status: "REJECTED",
        },
      ],
    });

    expect(await screen.findByText("Rejected")).toBeInTheDocument();
    expect(screen.getByText("Looks like a phishing page")).toBeInTheDocument();
  });
});
