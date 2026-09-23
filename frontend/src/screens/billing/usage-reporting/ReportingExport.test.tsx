import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { fakeFetch } from "@/test/fakeFetch";
import { renderWithProviders } from "@/test/render";

import { ReportingExport } from "./ReportingExport";

const FILTERS = {
  countries: "",
  products: "",
  senderIds: "",
  since: "2026-07-01",
  until: "2026-09-23",
  userIds: "",
} as const;

describe("ReportingExport", () => {
  it("describes what the export button downloads", () => {
    renderWithProviders(<ReportingExport filters={FILTERS} />, { fetcher: fakeFetch({}) });

    expect(screen.getByRole("button", { name: "EXPORT" })).toHaveAccessibleDescription(
      "Exports the current filter as CSV",
    );
  });
});
