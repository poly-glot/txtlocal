import type { QuickSendRequest, Refusal } from "@/api/generated/dashboard";
import { dateTimeIn } from "@/lib/format";

import type { ScreenProduct } from "../rules";

const COUNTRY_NOT_ENABLED = "COUNTRY_NOT_ENABLED";

const IMMEDIATELY_LABEL = "Immediately";

type RecipientKind = "CONTACT" | "LIST" | "NUMBER";

export interface Draft {
  body: string;
  kind: ScreenProduct;
  mediaKey: string | null;
  recipients: Recipient[];
  sendAt: string;
  senderId: string;
  shortenUrls: boolean;
  subject: string;
}

export interface Recipient {
  kind: RecipientKind;
  label: string;
  value: string;
}

export function emptyDraft(kind: ScreenProduct): Draft {
  return {
    body: "",
    kind,
    mediaKey: null,
    recipients: [],
    sendAt: "",
    senderId: "",
    shortenUrls: false,
    subject: "",
  };
}

export function confirmSendTitle(kind: ScreenProduct): string {
  return `Confirm ${kind} Send`;
}

export function hasNamedRecipient(recipients: readonly Recipient[]): boolean {
  return recipients.some((chip) => chip.kind !== "NUMBER");
}

export function isSendable(draft: Draft): boolean {
  if (draft.recipients.length === 0) {
    return false;
  }

  return draft.kind === "MMS" ? draft.mediaKey !== null : draft.body.trim() !== "";
}

export function quickSendRequest(draft: Draft): QuickSendRequest {
  return {
    body: draft.body,
    kind: draft.kind,
    listIds: valuesOf(draft.recipients, "LIST"),
    mediaKey: draft.mediaKey,
    messageType: "PROMOTIONAL",
    sendAt: draft.sendAt === "" ? null : new Date(draft.sendAt).toISOString(),
    senderId: draft.senderId === "" ? null : draft.senderId,
    shortenUrls: draft.shortenUrls,
    subject: draft.subject,
    to: draft.recipients.filter((chip) => chip.kind !== "LIST").map((chip) => chip.value),
  };
}

export function skippedSummary(refused: readonly Refusal[]): string | undefined {
  const skipped = refused.filter((entry) => entry.reason === COUNTRY_NOT_ENABLED).length;

  return skipped === 0 ? undefined : `${String(skipped)} recipients skipped (country not enabled)`;
}

export function deliverLabel(sendAt: string, timezone: string | undefined): string {
  return sendAt === "" ? IMMEDIATELY_LABEL : dateTimeIn(sendAt, timezone, "short");
}

function valuesOf(recipients: readonly Recipient[], kind: RecipientKind): string[] {
  return recipients.filter((chip) => chip.kind === kind).map((chip) => chip.value);
}
