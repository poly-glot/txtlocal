import type { MessageStatus, paths } from "@/api/generated/dashboard";

import type { ScreenProduct, StatusDisplay } from "../rules";

export type HistoryQuery = NonNullable<paths["/api/app/messages"]["get"]["parameters"]["query"]>;

const DAY_MS = 86_400_000;

export type HistoryPreset = "Last 30 days" | "Last 7 days" | "Today";

interface DateRange {
  from: string;
  to: string;
}

export const HISTORY_PRESETS: readonly HistoryPreset[] = ["Today", "Last 7 days", "Last 30 days"];

export const STATUS_DISPLAY: Record<MessageStatus, StatusDisplay> = {
  DELIVERED: { label: "Delivered", tone: "success" },
  FAILED: { label: "Failed", tone: "danger" },
  QUEUED: { label: "Queued", tone: "warning" },
  RECEIVED: { label: "Received", tone: "neutral" },
  SENT: { label: "Sent", tone: "accent" },
};

const PRESET_DAYS: Record<HistoryPreset, number> = {
  "Last 30 days": 30,
  "Last 7 days": 7,
  Today: 0,
};

export function historyTitle(product: ScreenProduct): string {
  return `${product} History`;
}

export function initialHistoryFilters(product: ScreenProduct): HistoryQuery {
  return product === "MMS" ? { field: "TO", kind: "MMS" } : { field: "TO" };
}

export function presetRange(preset: HistoryPreset, today: Date): DateRange {
  const since = new Date(today.getTime() - PRESET_DAYS[preset] * DAY_MS);

  return { from: dayValue(since), to: dayValue(today) };
}

function dayValue(date: Date): string {
  return date.toISOString().slice(0, 10);
}
