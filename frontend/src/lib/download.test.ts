import { afterEach, describe, expect, it, vi } from "vitest";

import { saveCsv } from "./download";

afterEach(() => {
  vi.restoreAllMocks();
});

describe("saveCsv", () => {
  it("downloads the text under the given file name", () => {
    const click = vi
      .spyOn(HTMLAnchorElement.prototype, "click")
      .mockImplementation(() => undefined);

    saveCsv("a,b\n1,2\n", "usage.csv");

    const anchor = click.mock.contexts[0];
    expect(anchor).toHaveAttribute("download", "usage.csv");
    expect(anchor).toHaveAttribute("href", "data:text/csv;charset=utf-8,a%2Cb%0A1%2C2%0A");
  });
});
