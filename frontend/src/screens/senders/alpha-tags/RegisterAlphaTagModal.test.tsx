import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { openTab, renderSenders } from "../testing";

async function openModal(user: ReturnType<typeof userEvent.setup>): Promise<void> {
  await openTab(user, "Alpha Tags");
  await user.click(screen.getByRole("button", { name: "+ Add" }));
}

describe("RegisterAlphaTagModal", () => {
  it("explains the rule and hints at the tag's shape", async () => {
    const user = userEvent.setup();
    renderSenders();

    await openModal(user);

    expect(
      screen.getByText(
        "You must register your alpha tag in order to start sending. Customers cannot reply to alpha tags. Some countries may need additional registration or block alpha tags.",
      ),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("Alpha Tag")).toHaveAccessibleDescription(
      "3-11 characters. Numbers, letters, pluses only.",
    );
  });

  it("keeps Register Alpha Tag disabled until the tag is a valid length", async () => {
    const user = userEvent.setup();
    renderSenders();
    await openModal(user);
    const button = screen.getByRole("button", { name: "Register Alpha Tag" });
    const field = screen.getByLabelText("Alpha Tag");

    expect(button).toBeDisabled();
    await user.type(field, "AB");
    expect(button).toBeDisabled();
    await user.type(field, "C");
    expect(button).toBeEnabled();
  });

  it("defaults the use case to Marketing", async () => {
    const user = userEvent.setup();
    renderSenders();

    await openModal(user);

    expect(screen.getByLabelText("Your Use Case")).toHaveValue("MARKETING");
  });

  it("closes without registering on Close", async () => {
    const user = userEvent.setup();
    renderSenders();
    await openModal(user);

    await user.click(screen.getByRole("button", { name: "Close" }));

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });
});
