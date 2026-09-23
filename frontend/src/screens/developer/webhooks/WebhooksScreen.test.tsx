import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { refusal } from "@/test/fakeFetch";
import { DEFAULT_RULE } from "@/test/fixtures/automation";

import { renderWebhooks } from "./testing";

describe("WebhooksScreen", () => {
  it("adds an inbound rule end to end", async () => {
    const user = userEvent.setup();
    const fetcher = renderWebhooks({ "POST /api/app/rules/inbound": {} });

    await screen.findByText("Default rule");
    const inboundRules = screen.getByRole("region", { name: "Inbound Rules" });
    await user.click(within(inboundRules).getByRole("button", { name: "ADD NEW RULE" }));
    await user.type(screen.getByLabelText("Rule Name"), "Forward sales");
    await user.click(screen.getByRole("button", { name: "ADD" }));

    expect(await screen.findByText("Inbound rule saved.")).toBeInTheDocument();
    const created = fetcher.calls.find(
      (call) => call.method === "POST" && call.path === "/api/app/rules/inbound",
    );
    expect(created?.body).toEqual({
      action: "EMAIL_USER",
      actionAddress: null,
      backupEmail: null,
      enabled: true,
      keyword: null,
      matchKind: "ANY",
      name: "Forward sales",
      number: null,
    });
  });

  it("shows a new delivery rule's signing secret once, then hides it after Done", async () => {
    const user = userEvent.setup();
    renderWebhooks({
      "POST /api/app/rules/delivery": {
        rule: {
          createdAt: "2026-09-19T10:00:00Z",
          enabled: true,
          events: "ALL",
          name: "New rule",
          ruleId: "delivery-2",
          url: "https://example.com/new",
        },
        secret: "whsec_topsecret",
      },
    });

    await screen.findByText("Order updates");
    const deliveryRules = screen.getByRole("region", { name: "Delivery Report Rules" });
    await user.click(within(deliveryRules).getByRole("button", { name: "ADD NEW RULE" }));
    await user.type(screen.getByLabelText("Rule Name"), "New rule");
    await user.type(screen.getByLabelText("URL"), "https://example.com/new");
    await user.click(screen.getByRole("button", { name: "ADD" }));

    expect(await screen.findByDisplayValue("whsec_topsecret")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Done" }));

    expect(screen.queryByDisplayValue("whsec_topsecret")).not.toBeInTheDocument();
  });

  it("renders the server's refusal of a new inbound rule verbatim", async () => {
    const user = userEvent.setup();
    renderWebhooks({
      "POST /api/app/rules/inbound": refusal(400, "A rule with this name already exists"),
    });

    await screen.findByText("Default rule");
    const inboundRules = screen.getByRole("region", { name: "Inbound Rules" });
    await user.click(within(inboundRules).getByRole("button", { name: "ADD NEW RULE" }));
    await user.type(screen.getByLabelText("Rule Name"), "Duplicate");
    await user.click(screen.getByRole("button", { name: "ADD" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "A rule with this name already exists",
    );
  });

  it("keeps the dialog open with the refusal when a delete is refused", async () => {
    const user = userEvent.setup();
    renderWebhooks({
      "DELETE /api/app/rules/inbound/rule-default": refusal(404, "Rule not found"),
    });

    await user.click(await screen.findByRole("button", { name: "Delete Default rule" }));
    const dialog = screen.getByRole("dialog");
    await user.click(within(dialog).getByRole("button", { name: "Delete" }));

    expect(await within(dialog).findByRole("alert")).toHaveTextContent("Rule not found");
    expect(screen.queryByText("Inbound rule deleted.")).not.toBeInTheDocument();
  });

  it("pages through rows beyond the chosen entries", async () => {
    const user = userEvent.setup();
    const rules = Array.from({ length: 21 }, (_, index) => ({
      ...DEFAULT_RULE,
      name: `Rule ${String(index + 1)}`,
      ruleId: `rule-${String(index + 1)}`,
    }));
    renderWebhooks({ "GET /api/app/rules/inbound": rules });

    await screen.findByText("Rule 20");
    const inboundRules = screen.getByRole("region", { name: "Inbound Rules" });
    expect(within(inboundRules).queryByText("Rule 21")).not.toBeInTheDocument();
    await user.click(within(inboundRules).getByRole("button", { name: "Next" }));

    expect(within(inboundRules).getByText("Rule 21")).toBeInTheDocument();
    expect(within(inboundRules).queryByText("Rule 20")).not.toBeInTheDocument();
  });

  describe.each([
    {
      panel: "Inbound Rules",
      refused: "Rule not found",
      route: "PUT /api/app/rules/inbound/rule-default",
      toggle: "Disable Default rule",
    },
    {
      panel: "Delivery Report Rules",
      refused: "Delivery report rule not found",
      route: "PUT /api/app/rules/delivery/delivery-1",
      toggle: "Disable Order updates",
    },
  ] as const)("$panel", ({ panel, refused, route, toggle }) => {
    it("shows the refusal when a rule cannot be toggled", async () => {
      const user = userEvent.setup();
      renderWebhooks({ [route]: refusal(404, refused) });

      await user.click(await screen.findByRole("button", { name: toggle }));

      const rules = screen.getByRole("region", { name: panel });
      expect(await within(rules).findByRole("alert")).toHaveTextContent(refused);
    });
  });
});
