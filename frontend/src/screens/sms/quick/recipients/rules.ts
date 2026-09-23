import type { ContactHit, ContactList } from "@/api/generated/dashboard";
import type { Result } from "@/types";

import type { Recipient } from "../rules";

export const CONTACT_SEARCH_LIMIT = 8;
export const CONTACT_SEARCH_MIN_CHARS = 2;

export const MAX_RECIPIENTS = 1_000;

export const TOO_MANY_RECIPIENTS_MSG = "Send to at most 1,000 recipients at a time";

export function contactRecipient(hit: ContactHit): Recipient {
  return {
    kind: "CONTACT",
    label: `${hit.firstName} ${hit.lastName} ${hit.mobile}`.trim(),
    value: hit.mobile,
  };
}

export function listRecipient(list: ContactList): Recipient {
  return {
    kind: "LIST",
    label: `${list.name} (${String(list.contactCount)})`,
    value: list.listId,
  };
}

export function sendableLists(lists: readonly ContactList[], q: string): ContactList[] {
  const wanted = q.trim().toLowerCase();

  return lists.filter(
    (list) => list.kind !== "OPT_OUT" && list.name.toLowerCase().includes(wanted),
  );
}

export function listById(
  lists: readonly ContactList[],
  listId: string | null,
): ContactList | undefined {
  return listId === null ? undefined : lists.find((list) => list.listId === listId);
}

export function addRecipient(
  recipients: readonly Recipient[],
  entry: Recipient,
): Result<Recipient[]> {
  if (recipients.some((chip) => chip.value === entry.value)) {
    return { data: [...recipients], status: "OK" };
  }
  if (recipients.length >= MAX_RECIPIENTS) {
    return { message: TOO_MANY_RECIPIENTS_MSG, status: "ERROR" };
  }

  return { data: [...recipients, entry], status: "OK" };
}

export function withoutRecipient(recipients: readonly Recipient[], value: string): Recipient[] {
  return recipients.filter((chip) => chip.value !== value);
}
