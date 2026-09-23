import { describe, expect, it } from "vitest";

import { EXAMPLE_LIST, OPT_OUT_LIST } from "@/test/fixtures/contacts";

import { EMPTY_CONTACT } from "../rules";
import {
  IMPORT_CHUNK_ROWS,
  MISSING_MOBILE_COLUMN_MSG,
  NO_IMPORTS,
  chunksOf,
  contactsLabel,
  csvRows,
  importRows,
  importSummary,
  isOptOut,
  withReport,
} from "./rules";

const rowsOfLength = (count: number) => Array.from({ length: count }, () => EMPTY_CONTACT);

describe("csvRows", () => {
  it.each([
    { label: "splits a plain line", text: "a,b,c", values: ["a", "b", "c"] },
    { label: "keeps a comma inside quotes", text: '"a,b",c', values: ["a,b", "c"] },
    { label: "unescapes a doubled quote", text: '"a""b",c', values: ['a"b', "c"] },
    { label: "trims surrounding spaces", text: " a , b ", values: ["a", "b"] },
    { label: "keeps an empty value", text: "a,,c", values: ["a", "", "c"] },
  ] as const)("$label", ({ text, values }) => {
    expect(csvRows(text)).toEqual([values]);
  });

  it("drops a blank line", () => {
    expect(csvRows("a\n\nb\r\n")).toEqual([["a"], ["b"]]);
  });
});

describe("importRows", () => {
  it("maps the header names to contact fields", () => {
    const text =
      "mobile,first_name,last_name,email,cf1,cf2,cf3,cf4\n+447400123123,Sam,Ray,s@e.com,a,b,c,d";

    expect(importRows(text)).toEqual({
      data: [
        {
          cf1: "a",
          cf2: "b",
          cf3: "c",
          cf4: "d",
          email: "s@e.com",
          firstName: "Sam",
          lastName: "Ray",
          mobile: "+447400123123",
        },
      ],
      status: "OK",
    });
  });

  it.each([
    { header: "Mobile", label: "ignores the case of a header" },
    { header: "  mobile  ", label: "ignores space around a header" },
  ] as const)("$label", ({ header }) => {
    expect(importRows(`${header}\n+447400123123`)).toEqual({
      data: [{ ...EMPTY_CONTACT, mobile: "+447400123123" }],
      status: "OK",
    });
  });

  it("reads First Name as the first name column", () => {
    const parsed = importRows("mobile,First Name\n+447400123123,Sam");

    expect(parsed).toEqual({
      data: [{ ...EMPTY_CONTACT, firstName: "Sam", mobile: "+447400123123" }],
      status: "OK",
    });
  });

  it("refuses a CSV without a mobile column", () => {
    expect(importRows("first_name\nSam")).toEqual({
      message: MISSING_MOBILE_COLUMN_MSG,
      status: "ERROR",
    });
  });

  it("refuses an empty file", () => {
    expect(importRows("")).toEqual({ message: MISSING_MOBILE_COLUMN_MSG, status: "ERROR" });
  });
});

describe("chunksOf", () => {
  it.each([
    { label: "sends 500 rows as one request", lengths: [500], rows: 500 },
    { label: "sends 501 rows as two requests", lengths: [500, 1], rows: 501 },
    { label: "sends 1,000 rows as two requests", lengths: [500, 500], rows: 1000 },
    { label: "sends 1,001 rows as three requests", lengths: [500, 500, 1], rows: 1001 },
    { label: "sends nothing for no rows", lengths: [], rows: 0 },
  ] as const)("$label", ({ lengths, rows }) => {
    expect(chunksOf(rowsOfLength(rows)).map((chunk) => chunk.length)).toEqual(lengths);
  });

  it("chunks at the documented ceiling", () => {
    expect(IMPORT_CHUNK_ROWS).toBe(500);
  });
});

describe("importSummary", () => {
  it("sums the reports of every chunk into one sentence", () => {
    const first = withReport(NO_IMPORTS, { imported: 2, message: "", skipped: 1, updated: 0 });
    const both = withReport(first, { imported: 1, message: "", skipped: 0, updated: 3 });

    expect(importSummary(both)).toBe("Imported 3, updated 3, skipped 1 invalid");
  });
});

describe("labels", () => {
  it.each([
    { count: 0, expected: "0 contacts", label: "none" },
    { count: 1, expected: "1 contact", label: "one" },
    { count: 2, expected: "2 contacts", label: "more than one" },
  ] as const)("counts $label", ({ count, expected }) => {
    expect(contactsLabel(count)).toBe(expected);
  });

  it("knows the opt-out list", () => {
    expect(isOptOut(OPT_OUT_LIST)).toBe(true);
  });

  it("knows a standard list is not the opt-out list", () => {
    expect(isOptOut(EXAMPLE_LIST)).toBe(false);
  });
});
