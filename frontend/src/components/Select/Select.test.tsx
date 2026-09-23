import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ChangeEvent } from "react";
import { describe, expect, it, vi } from "vitest";

import { Select } from "./Select";

const OPTIONS = [
  { label: "No", value: "false" },
  { label: "Yes", value: "true" },
];

describe("Select", () => {
  it("reports the chosen value", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn((event: ChangeEvent<HTMLSelectElement>) => event.target.value);
    render(<Select id="own" label="Show own number" onChange={onChange} options={OPTIONS} />);

    await user.selectOptions(screen.getByLabelText("Show own number"), "Yes");

    expect(onChange).toHaveReturnedWith("true");
  });
});
