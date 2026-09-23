import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { Modal } from "./Modal";

function renderModal(onClose = vi.fn()) {
  render(
    <Modal labelledBy="title" onClose={onClose}>
      <Modal.Header>
        <Modal.Title id="title">Your new API key</Modal.Title>
      </Modal.Header>
      <Modal.Body>Store this key now.</Modal.Body>
      <Modal.Footer>
        <button onClick={onClose} type="button">
          Done
        </button>
      </Modal.Footer>
    </Modal>,
  );

  return onClose;
}

describe("Modal", () => {
  it("is a dialog named by its header", () => {
    renderModal();

    expect(screen.getByRole("dialog", { name: "Your new API key" })).toBeInTheDocument();
  });

  it("heads the dialog with its title", () => {
    renderModal();

    expect(screen.getByRole("heading", { level: 2, name: "Your new API key" })).toBeInTheDocument();
  });

  it("closes on Escape", async () => {
    const user = userEvent.setup();
    const onClose = renderModal();

    await user.keyboard("{Escape}");

    expect(onClose).toHaveBeenCalledOnce();
  });
});
