import type { Product, SendersView } from "@/api/generated/dashboard";
import type { Tone } from "@/components/Badge/Badge";

export const LOADING_MSG = "Loading…";
export const NOW_LABEL = "Now";
export const SMART_SENDERS_LABEL = "Smart Senders";

export type ScreenProduct = Extract<Product, "MMS" | "SMS">;

export interface StatusDisplay {
  label: string;
  tone: Tone;
}

export function senderDisplayOf(view: SendersView, senderId: string): string {
  const senders = Object.values(view.senders).flat();

  return senders.find((sender) => sender.senderId === senderId)?.display ?? SMART_SENDERS_LABEL;
}

const MINUTE_MS = 60_000;
const MINUTES_AHEAD_MIN = 5;
const MONTHS_AHEAD_MAX = 12;

export function earliestSendAt(now: Date): Date {
  return new Date(now.getTime() + MINUTES_AHEAD_MIN * MINUTE_MS);
}

export function latestSendAt(now: Date): Date {
  const latest = new Date(now.getTime());
  latest.setMonth(latest.getMonth() + MONTHS_AHEAD_MAX);

  return latest;
}
