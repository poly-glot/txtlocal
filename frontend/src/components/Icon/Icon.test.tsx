import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Icon } from "./Icon";

describe("Icon", () => {
  it("hides itself from assistive technology", () => {
    const { container } = render(<Icon name="home" />);

    expect(container.querySelector("svg")).toHaveAttribute("aria-hidden", "true");
  });

  it("draws at the size it was given", () => {
    const { container } = render(<Icon name="bell" size={20} />);

    expect(container.querySelector("svg")).toHaveAttribute("width", "20");
  });
});
