import type {
  EmailSenderRequest,
  SenderView,
  SendersView,
  UserRow,
} from "@/api/generated/dashboard";
import type { Option } from "@/components/Select/Select";

export type SubaccountOption = Pick<UserRow, "userId" | "username">;

export interface EmailSenderDraft {
  email: string;
  senderId: string;
  userId: string;
}

export const EMPTY_EMAIL_SENDER_DRAFT: EmailSenderDraft = { email: "", senderId: "", userId: "" };

export function emailSenderRequestOf(draft: EmailSenderDraft): EmailSenderRequest {
  return { email: draft.email, senderId: draft.senderId, userId: draft.userId };
}

export function isEmailSenderSaveable(draft: EmailSenderDraft): boolean {
  return draft.email.trim() !== "" && draft.senderId !== "" && draft.userId !== "";
}

export function readySenders(view: SendersView): SenderView[] {
  return Object.values(view.senders)
    .flat()
    .filter((sender) => sender.status === "READY");
}

export function senderDisplay(view: SendersView, senderId: string | null): string {
  if (senderId === null) {
    return "";
  }

  const sender = Object.values(view.senders)
    .flat()
    .find((candidate) => candidate.senderId === senderId);

  return sender?.display ?? senderId;
}

export function subaccountLabel(subaccounts: readonly SubaccountOption[], userId: string): string {
  return subaccounts.find((subaccount) => subaccount.userId === userId)?.username ?? userId;
}

export function subaccountOptions(subaccounts: readonly SubaccountOption[]): Option[] {
  return subaccounts.map((subaccount) => ({
    label: subaccount.username,
    value: subaccount.userId,
  }));
}

export function readySenderOptions(senders: readonly SenderView[]): Option[] {
  return senders.map((sender) => ({ label: sender.display, value: sender.senderId }));
}
