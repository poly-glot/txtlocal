import type { ContactInput, ContactList, ImportReport } from "@/api/generated/dashboard";
import type { Result } from "@/types";

import { EMPTY_CONTACT } from "../rules";

const QUOTED_VALUE = /^"(.*)"$/su;
const SEPARATOR_CHARS = /[\s-]+/gu;

export const IMPORT_CHUNK_ROWS = 500;
export const MAX_LIST_NAME_CHARS = 100;
export const MISSING_MOBILE_COLUMN_MSG = "The CSV needs a mobile column";
const HEADER_FIELDS: Readonly<Record<string, keyof ContactInput>> = {
  cf1: "cf1",
  cf2: "cf2",
  cf3: "cf3",
  cf4: "cf4",
  email: "email",
  first_name: "firstName",
  last_name: "lastName",
  mobile: "mobile",
};

interface ImportTotals {
  imported: number;
  skipped: number;
  updated: number;
}

export interface ListDraft {
  listId: string | null;
  name: string;
}

export const NO_IMPORTS: ImportTotals = { imported: 0, skipped: 0, updated: 0 };

export const isOptOut = (list: ContactList) => list.kind === "OPT_OUT";

export const contactsLabel = (count: number) =>
  `${String(count)} ${count === 1 ? "contact" : "contacts"}`;

export const newList = (): ListDraft => ({ listId: null, name: "" });

export const renameDraft = (list: ContactList): ListDraft => ({
  listId: list.listId,
  name: list.name,
});

export const csvName = (list: ContactList) => `${list.name}.csv`;

export function csvRows(text: string): string[][] {
  return text
    .split(/\r?\n/u)
    .filter((line) => line.trim() !== "")
    .map(splitLine);
}

export function importRows(text: string): Result<ContactInput[]> {
  const [header = [], ...lines] = csvRows(text);
  const fields = header.map((name) => HEADER_FIELDS[normalisedHeader(name)]);
  if (!fields.includes("mobile")) {
    return { message: MISSING_MOBILE_COLUMN_MSG, status: "ERROR" };
  }

  return { data: lines.map((values) => rowOf(fields, values)), status: "OK" };
}

export function chunksOf(rows: readonly ContactInput[]): ContactInput[][] {
  const chunks: ContactInput[][] = [];
  for (let start = 0; start < rows.length; start += IMPORT_CHUNK_ROWS) {
    chunks.push(rows.slice(start, start + IMPORT_CHUNK_ROWS));
  }

  return chunks;
}

export function withReport(totals: ImportTotals, report: ImportReport): ImportTotals {
  return {
    imported: totals.imported + report.imported,
    skipped: totals.skipped + report.skipped,
    updated: totals.updated + report.updated,
  };
}

export function importSummary(totals: ImportTotals): string {
  return `Imported ${String(totals.imported)}, updated ${String(totals.updated)}, skipped ${String(totals.skipped)} invalid`;
}

function rowOf(
  fields: readonly (keyof ContactInput | undefined)[],
  values: string[],
): ContactInput {
  const row = { ...EMPTY_CONTACT };
  fields.forEach((field, index) => {
    if (field !== undefined) {
      row[field] = values[index] ?? "";
    }
  });

  return row;
}

function normalisedHeader(name: string): string {
  return name.trim().toLowerCase().replaceAll(SEPARATOR_CHARS, "_");
}

function splitLine(line: string): string[] {
  const values: string[] = [];
  let current = "";
  let quoted = false;

  for (const char of line) {
    if (char === '"') {
      quoted = !quoted;
    }
    if (char === "," && !quoted) {
      values.push(current);
      current = "";
      continue;
    }
    current += char;
  }
  values.push(current);

  return values.map(unquoted);
}

function unquoted(value: string): string {
  const trimmed = value.trim();
  const quoted = QUOTED_VALUE.exec(trimmed);

  return quoted === null ? trimmed : (quoted[1] ?? "").replaceAll('""', '"');
}
