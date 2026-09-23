import type {
  ActionResult,
  CleanUpRequest,
  Contact,
  ContactInput,
} from "@/api/generated/dashboard";
import type { Notice, Result } from "@/types";

import { EMPTY_CONTACT } from "../rules";

const MAX_CUSTOM_FIELD_CHARS = 100;
const MAX_NAME_CHARS = 50;

const SORT_VALUES: Readonly<Record<string, (contact: Contact) => string>> = {
  cf1: (contact) => contact.cf1,
  cf2: (contact) => contact.cf2,
  cf3: (contact) => contact.cf3,
  cf4: (contact) => contact.cf4,
  email: (contact) => contact.email,
  firstName: (contact) => contact.firstName,
  lastName: (contact) => contact.lastName,
  mobile: (contact) => contact.mobile,
  updatedAt: (contact) => contact.updatedAt,
};

export interface ContactEdit {
  contactId: string | null;
  input: ContactInput;
}

interface ContactField {
  label: string;
  maxLength?: number;
  name: keyof ContactInput;
  required?: true;
  type?: string;
}

export const CONTACT_FIELDS: readonly ContactField[] = [
  { label: "First Name", maxLength: MAX_NAME_CHARS, name: "firstName" },
  { label: "Last Name", maxLength: MAX_NAME_CHARS, name: "lastName" },
  { label: "Mobile", name: "mobile", required: true, type: "tel" },
  { label: "Email", name: "email", type: "email" },
  { label: "CF1", maxLength: MAX_CUSTOM_FIELD_CHARS, name: "cf1" },
  { label: "CF2", maxLength: MAX_CUSTOM_FIELD_CHARS, name: "cf2" },
  { label: "CF3", maxLength: MAX_CUSTOM_FIELD_CHARS, name: "cf3" },
  { label: "CF4", maxLength: MAX_CUSTOM_FIELD_CHARS, name: "cf4" },
];

export const isCleanUpAction = (value: string): value is CleanUpRequest["action"] =>
  value === "INVALID" || value === "OPTED_OUT";

export const newContact = (): ContactEdit => ({ contactId: null, input: EMPTY_CONTACT });

export const sortValueOf = (contact: Contact, key: string) => SORT_VALUES[key]?.(contact) ?? "";

export function editOf(contact: Contact): ContactEdit {
  return {
    contactId: contact.mobile,
    input: {
      cf1: contact.cf1,
      cf2: contact.cf2,
      cf3: contact.cf3,
      cf4: contact.cf4,
      email: contact.email,
      firstName: contact.firstName,
      lastName: contact.lastName,
      mobile: contact.mobile,
    },
  };
}

export function actionNotice(result: Result<ActionResult>): Notice {
  return result.status === "OK"
    ? { message: result.data.message, tone: "success" }
    : { message: result.message, tone: "error" };
}

export function toggledOne(selected: ReadonlySet<string>, mobile: string): ReadonlySet<string> {
  const next = new Set(selected);
  if (!next.delete(mobile)) {
    next.add(mobile);
  }

  return next;
}

export function toggledAll(
  mobiles: readonly string[],
  selected: ReadonlySet<string>,
): ReadonlySet<string> {
  return mobiles.every((mobile) => selected.has(mobile)) ? new Set<string>() : new Set(mobiles);
}
