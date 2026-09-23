import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { EMAIL_SENDER } from "@/test/fixtures/automation";

import { renderEmailSms } from "./testing";

describe("EmailSmsScreen", () => {
  it("shows the coming-soon note under the heading", async () => {
    renderEmailSms();

    expect(await screen.findByRole("heading", { name: "Email SMS" })).toBeInTheDocument();
    expect(screen.getByText("Email to SMS is coming soon")).toBeInTheDocument();
  });

  it("lists an existing allowed address by subaccount, email and sender", async () => {
    renderEmailSms();

    expect(await screen.findByText("demo@txtlocal.local")).toBeInTheDocument();
    expect(screen.getByText("sales@txtlocal.local")).toBeInTheDocument();
    expect(screen.getByText("Shared Number")).toBeInTheDocument();
  });

  it("adds an allowed address end to end", async () => {
    const user = userEvent.setup();
    const fetcher = renderEmailSms({
      "POST /api/app/email-senders": {
        email: "new@txtlocal.local",
        senderId: "sender-dedicated",
        userId: "user-1",
      },
    });

    await user.click(await screen.findByRole("button", { name: "ADD" }));
    const dialog = screen.getByRole("dialog");
    await user.selectOptions(within(dialog).getByLabelText("Subaccount"), "user-1");
    await user.type(within(dialog).getByLabelText("Email Address"), "new@txtlocal.local");
    await user.selectOptions(within(dialog).getByLabelText("Sender"), "sender-dedicated");
    await user.click(within(dialog).getByRole("button", { name: "ADD" }));

    expect(await screen.findByText("Allowed address added.")).toBeInTheDocument();
    const created = fetcher.calls.find((call) => call.method === "POST");
    expect(created?.body).toEqual({
      email: "new@txtlocal.local",
      senderId: "sender-dedicated",
      userId: "user-1",
    });
  });

  it("pages through rows beyond the chosen entries", async () => {
    const user = userEvent.setup();
    const addresses = Array.from({ length: 21 }, (_, index) => ({
      ...EMAIL_SENDER,
      email: `sender${String(index + 1)}@txtlocal.local`,
    }));
    renderEmailSms({ "GET /api/app/email-senders": addresses });

    await screen.findByText("sender20@txtlocal.local");
    const allowedAddresses = screen.getByRole("region", { name: "Allowed Addresses" });
    expect(within(allowedAddresses).queryByText("sender21@txtlocal.local")).not.toBeInTheDocument();
    await user.click(within(allowedAddresses).getByRole("button", { name: "Next" }));

    expect(within(allowedAddresses).getByText("sender21@txtlocal.local")).toBeInTheDocument();
    expect(within(allowedAddresses).queryByText("sender20@txtlocal.local")).not.toBeInTheDocument();
  });
});
