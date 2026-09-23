import type { Contact, ContactList } from "@/api/generated/dashboard";

import { ME } from "./identity";

export const EXAMPLE_LIST_ID = "list-example";
export const OPT_OUT_LIST_ID = "list-opt-out";

export const EXAMPLE_LIST: ContactList = {
  contactCount: 2,
  createdAt: "2026-09-19T12:00:00Z",
  kind: "STANDARD",
  listId: EXAMPLE_LIST_ID,
  name: "Example List",
};

export const OPT_OUT_LIST: ContactList = {
  contactCount: 0,
  createdAt: "2026-09-19T12:00:00Z",
  kind: "OPT_OUT",
  listId: OPT_OUT_LIST_ID,
  name: "Opt-Out List",
};

export const SAM: Contact = {
  accountId: ME.accountId,
  cf1: "Gold",
  cf2: "",
  cf3: "",
  cf4: "",
  email: "sam@example.com",
  firstName: "Sam",
  lastName: "Ray",
  listId: EXAMPLE_LIST_ID,
  mobile: "+447400123123",
  updatedAt: "2026-09-19T12:00:00Z",
};

export const ALEX: Contact = {
  ...SAM,
  cf1: "",
  email: "alex@example.com",
  firstName: "Alex",
  lastName: "Bell",
  mobile: "+447400999888",
  updatedAt: "2026-09-18T09:30:00Z",
};

export const CONTACTS_PATH = `/api/app/lists/${EXAMPLE_LIST_ID}/contacts`;
export const OPT_OUT_CONTACTS_PATH = `/api/app/lists/${OPT_OUT_LIST_ID}/contacts`;
