import type { ConversationStatus, MessageStatus, SendersView } from "@/api/generated/dashboard";
import type { Option } from "@/components/Select/Select";

export const SHARED_SENDER_VALUE = "";

const TICKS: Record<MessageStatus, string> = {
  DELIVERED: "✓✓",
  FAILED: "!",
  QUEUED: "…",
  RECEIVED: "✓",
  SENT: "✓",
};

export function toggleStatusLabel(status: ConversationStatus): string {
  return status === "OPEN" ? "Close conversation" : "Reopen conversation";
}

export function tickOf(status: MessageStatus): string {
  return TICKS[status];
}

export function chronological<T>(items: readonly T[]): T[] {
  return [...items].reverse();
}

export function defaultSenderId(lastSenderId: string | null | undefined): string {
  return lastSenderId ?? SHARED_SENDER_VALUE;
}

export function senderIdOf(choice: string): string | null {
  return choice === SHARED_SENDER_VALUE ? null : choice;
}

export function senderOptions(senders: SendersView["senders"]): Option[] {
  const flat = Object.values(senders)
    .flat()
    .map((sender) => ({ label: sender.display, value: sender.senderId }));

  return [{ label: "Smart Senders", value: SHARED_SENDER_VALUE }, ...flat];
}
