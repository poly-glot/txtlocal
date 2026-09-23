import type { CreateUser, UserRow } from "@/api/generated/dashboard";
import type { Sort } from "@/components/Table/Table";

export interface SubaccountDraft {
  firstName: string;
  lastName: string;
  notes: string;
  phone: string;
  username: string;
}

interface SubaccountField {
  label: string;
  maxLength?: number;
  name: keyof SubaccountDraft;
  required?: boolean;
  type?: string;
}

const NOTES_MAX_CHARS = 200;

export const EMPTY_SUBACCOUNT: SubaccountDraft = {
  firstName: "",
  lastName: "",
  notes: "",
  phone: "",
  username: "",
};

export const SUBACCOUNT_FIELDS: readonly SubaccountField[] = [
  { label: "Username / Email", name: "username", required: true, type: "email" },
  { label: "First Name", name: "firstName" },
  { label: "Last Name", name: "lastName" },
  { label: "Phone Number", name: "phone", type: "tel" },
  { label: "Notes", maxLength: NOTES_MAX_CHARS, name: "notes" },
];

export function toNewSubaccount(draft: SubaccountDraft): CreateUser {
  const subaccount: CreateUser = {
    firstName: draft.firstName,
    lastName: draft.lastName,
    username: draft.username,
  };
  for (const field of ["notes", "phone"] as const) {
    if (draft[field] !== "") {
      subaccount[field] = draft[field];
    }
  }

  return subaccount;
}

export function sortSubaccounts(rows: readonly UserRow[], sort: Sort): UserRow[] {
  const direction = sort.direction === "asc" ? 1 : -1;

  return [...rows].sort(
    (left, right) =>
      direction * sortValue(left, sort.key).localeCompare(sortValue(right, sort.key)),
  );
}

function sortValue(row: UserRow, key: string): string {
  switch (key) {
    case "apiKey":
      return row.apiKeyPrefix;
    case "notes":
      return row.notes ?? "";
    case "phone":
      return row.phone ?? "";
    default:
      return row.username;
  }
}
