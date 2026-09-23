import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { Toast } from "./Toast";

describe("Toast", () => {
  it("renders nothing without a notice", () => {
    render(<Toast notice={undefined} onDismiss={vi.fn()} />);

    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });

  it("announces an error as an alert", () => {
    render(
      <Toast notice={{ message: "Your balance is £0.00", tone: "error" }} onDismiss={vi.fn()} />,
    );

    expect(screen.getByRole("alert")).toHaveTextContent("Your balance is £0.00");
  });

  it("can be dismissed", async () => {
    const user = userEvent.setup();
    const onDismiss = vi.fn();
    render(<Toast notice={{ message: "Profile saved.", tone: "success" }} onDismiss={onDismiss} />);

    await user.click(screen.getByRole("button", { name: "Dismiss" }));

    expect(onDismiss).toHaveBeenCalledOnce();
  });
});
