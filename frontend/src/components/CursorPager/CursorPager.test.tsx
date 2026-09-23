import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { CursorTrail } from "@/lib/useCursorTrail";

import { CursorPager } from "./CursorPager";

const trailAt = (hasPrevious: boolean): CursorTrail => ({
  cursor: undefined,
  hasPrevious,
  next: vi.fn(),
  previous: vi.fn(),
});

describe("CursorPager", () => {
  it("offers no previous page on the first page", () => {
    render(<CursorPager nextCursor="page-2" trail={trailAt(false)} />);

    expect(screen.getByRole("button", { name: "Previous" })).toBeDisabled();
  });

  it("offers no next page when the server answered no cursor", () => {
    render(<CursorPager nextCursor={null} trail={trailAt(true)} />);

    expect(screen.getByRole("button", { name: "Next" })).toBeDisabled();
  });

  it("follows the cursor the server answered", async () => {
    const user = userEvent.setup();
    const trail = trailAt(false);
    render(<CursorPager nextCursor="page-2" trail={trail} />);

    await user.click(screen.getByRole("button", { name: "Next" }));

    expect(trail.next).toHaveBeenCalledWith("page-2");
  });
});
