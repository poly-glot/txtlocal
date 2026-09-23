import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { refusal } from "@/test/fakeFetch";

import { addOwnNumber, openTab, renderSenders } from "../testing";

async function openModal(user: ReturnType<typeof userEvent.setup>): Promise<void> {
  await openTab(user, "My Numbers");
  await user.click(screen.getByRole("button", { name: "+ Add" }));
}

describe("AddOwnNumberModal", () => {
  it("explains the steps and holds Send Code until a number is typed", async () => {
    const user = userEvent.setup();
    renderSenders();

    await openModal(user);

    expect(
      screen.getByText(
        "Follow the steps below to add your own number. We'll send you a code to verify your number.",
      ),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("Your Own Number")).toHaveAccessibleDescription(
      "Standard SMS charges apply.",
    );
    expect(screen.getByRole("button", { name: "Send Code" })).toBeDisabled();
    expect(screen.getByLabelText("Verification Code")).toBeDisabled();
  });

  it("holds Add Number until six digits are entered", async () => {
    const user = userEvent.setup();
    renderSenders();

    await openModal(user);
    await user.type(screen.getByLabelText("Your Own Number"), "07400123123");
    await user.click(screen.getByRole("button", { name: "Send Code" }));
    await user.type(await screen.findByLabelText("Verification Code"), "00000");

    expect(screen.getByRole("button", { name: "Add Number" })).toBeDisabled();
    await user.type(screen.getByLabelText("Verification Code"), "0");
    expect(screen.getByRole("button", { name: "Add Number" })).toBeEnabled();
  });

  it("sends the code to the number in international format and verifies it", async () => {
    const user = userEvent.setup();
    const fetcher = renderSenders();

    await addOwnNumber(user, "000000");

    const add = fetcher.calls.find((call) => call.path === "/api/app/senders/own");
    expect(add?.body).toEqual({ nickname: "New phone", number: "+447400123123" });
    const verify = fetcher.calls.find((call) => call.path.endsWith("/verify"));
    expect(verify?.body).toEqual({ code: "000000" });
  });

  it("closes once the number is verified", async () => {
    const user = userEvent.setup();
    renderSenders();

    await addOwnNumber(user, "000000");

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("renders the server's refusal of a wrong code verbatim", async () => {
    const user = userEvent.setup();
    renderSenders({
      "POST /api/app/senders/own/sender-pending/verify": refusal(
        400,
        "The code you entered is not correct",
      ),
    });

    await addOwnNumber(user, "111111");

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "The code you entered is not correct",
    );
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });
});
