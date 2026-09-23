import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { field, refusal } from "@/test/fakeFetch";
import { GENERAL } from "@/test/fixtures/billing";

import { renderGeneralScreen } from "./testing";

const ALERT_THRESHOLD = "Send me an Email/SMS when my account balance goes below:";
const AUTO_RECHARGE = "Automatically top up my account";
const LEGACY_MICRO = 15_000_000;
const RECHARGE_AMOUNT = "Top up by";
const RECHARGE_THRESHOLD = "When my balance goes below";

describe("GeneralScreen", () => {
  it("loads the current general settings", async () => {
    renderGeneralScreen();

    expect(await screen.findByLabelText("Account Name")).toHaveValue(GENERAL.name);
    expect(screen.getByLabelText("Account Email")).toHaveValue(GENERAL.email);
    expect(screen.getByLabelText("Account Mobile")).toHaveValue("+447700900123");
    expect(screen.getByRole("switch", { name: AUTO_RECHARGE })).not.toBeChecked();
  });

  it("explains that a dedicated number enables auto recharge", async () => {
    renderGeneralScreen();

    expect(await screen.findByRole("switch", { name: AUTO_RECHARGE })).toHaveAccessibleDescription(
      "If you purchase a dedicated number, auto recharge will be automatically enabled at the end of each month. This can be stopped by cancelling the number.",
    );
  });

  it("hides the recharge controls while auto recharge is off", async () => {
    renderGeneralScreen();
    await screen.findByRole("switch", { name: AUTO_RECHARGE });

    expect(screen.queryByLabelText(RECHARGE_AMOUNT)).not.toBeInTheDocument();
    expect(screen.queryByLabelText(RECHARGE_THRESHOLD)).not.toBeInTheDocument();
  });

  it("offers the four boosts to top up by, ten pounds first", async () => {
    const user = userEvent.setup();
    renderGeneralScreen();

    await user.click(await screen.findByRole("switch", { name: AUTO_RECHARGE }));

    const amount = screen.getByRole("combobox", { name: RECHARGE_AMOUNT });
    expect(amount).toHaveDisplayValue("£10");
    expect(optionLabels(amount)).toEqual(["£10", "£30", "£50", "£100"]);
  });

  it("offers four balances to recharge below, five pounds first", async () => {
    const user = userEvent.setup();
    renderGeneralScreen();

    await user.click(await screen.findByRole("switch", { name: AUTO_RECHARGE }));

    const threshold = screen.getByRole("combobox", { name: RECHARGE_THRESHOLD });
    expect(threshold).toHaveDisplayValue("£5.00");
    expect(optionLabels(threshold)).toEqual(["£5.00", "£10.00", "£20.00", "£50.00"]);
  });

  it("offers four balances to be alerted below, five pounds first", async () => {
    renderGeneralScreen();

    const alert = await screen.findByRole("combobox", { name: ALERT_THRESHOLD });
    expect(alert).toHaveDisplayValue("£5.00");
    expect(optionLabels(alert)).toEqual(["£5.00", "£10.00", "£20.00", "£50.00"]);
  });

  it.each([
    { key: "rechargeAmountMicro", label: "recharge amount", name: RECHARGE_AMOUNT },
    { key: "lowBalanceThresholdMicro", label: "recharge threshold", name: RECHARGE_THRESHOLD },
    { key: "alertThresholdMicro", label: "alert threshold", name: ALERT_THRESHOLD },
  ])("shows a saved $label that is no longer a choice", async ({ key, name }) => {
    renderGeneralScreen({
      "GET /api/app/billing/general": { ...GENERAL, autoRecharge: true, [key]: LEGACY_MICRO },
    });

    expect(await screen.findByRole("combobox", { name })).toHaveDisplayValue("£15.00");
  });

  it("saves the chosen alert threshold in micro-pounds", async () => {
    const user = userEvent.setup();
    const fetcher = renderGeneralScreen({ "PUT /api/app/billing/general": GENERAL });

    await user.selectOptions(
      await screen.findByRole("combobox", { name: ALERT_THRESHOLD }),
      "£20.00",
    );
    await user.click(screen.getByRole("button", { name: "Save" }));

    await screen.findByText("Settings saved.");
    const put = fetcher.calls.find((call) => call.method === "PUT");
    expect(field(put, "alertThresholdMicro")).toBe(20_000_000);
  });

  it.each([
    { field: "Account Name", title: "Billing Contact" },
    { field: ALERT_THRESHOLD, title: "Balance Management" },
  ])("collapses $title to its header", async ({ field: label, title }) => {
    const user = userEvent.setup();
    renderGeneralScreen();

    await user.click(await screen.findByText(title));

    expect(screen.getByLabelText(label)).not.toBeVisible();
  });

  it("saves the updated settings and confirms", async () => {
    const user = userEvent.setup();
    const fetcher = renderGeneralScreen({ "PUT /api/app/billing/general": GENERAL });
    const name = await screen.findByLabelText("Account Name");

    await user.clear(name);
    await user.type(name, "New Name Ltd");
    await user.click(screen.getByRole("switch", { name: AUTO_RECHARGE }));
    await user.click(screen.getByRole("button", { name: "Save" }));

    expect(await screen.findByText("Settings saved.")).toBeInTheDocument();
    const put = fetcher.calls.find((call) => call.method === "PUT");
    expect(field(put, "name")).toBe("New Name Ltd");
    expect(field(put, "autoRecharge")).toBe(true);
  });

  it("renders the server's refusal verbatim", async () => {
    const user = userEvent.setup();
    renderGeneralScreen({
      "PUT /api/app/billing/general": refusal(400, "Enter a valid email address"),
    });
    await screen.findByLabelText("Account Name");

    await user.click(screen.getByRole("button", { name: "Save" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Enter a valid email address");
  });
});

function optionLabels(select: HTMLElement): string[] {
  return within(select)
    .getAllByRole("option")
    .map((option) => option.textContent);
}
