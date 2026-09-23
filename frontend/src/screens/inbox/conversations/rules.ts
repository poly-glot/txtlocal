import type { ConversationStatus } from "@/api/generated/dashboard";
import type { Option } from "@/components/Select/Select";
import { dateTimeIn } from "@/lib/format";

const DAY_MS = 86_400_000;
const HOUR_MS = 3_600_000;
const MINUTE_MS = 60_000;
const WEEK_MS = 7 * DAY_MS;

const MAX_NUMBER_DIGITS = 15;
const MIN_NUMBER_DIGITS = 7;
const NUMBER_PATTERN = /^\+?\d+$/u;

export type StatusFilter = "ALL" | "CLOSED" | "OPEN";

export const STATUS_OPTIONS: readonly Option[] = [
  { label: "Open", value: "OPEN" },
  { label: "Closed", value: "CLOSED" },
  { label: "All", value: "ALL" },
];

export function statusFilterOf(value: string): StatusFilter {
  switch (value) {
    case "ALL":
      return "ALL";
    case "CLOSED":
      return "CLOSED";
    default:
      return "OPEN";
  }
}

export function statusQueryValue(filter: StatusFilter): ConversationStatus | null {
  return filter === "ALL" ? null : filter;
}

export function initialsOf(name: string): string {
  const letters = name
    .trim()
    .split(/\s+/u)
    .filter((word) => /[A-Za-z]/u.test(word))
    .map((word) => word.charAt(0).toUpperCase());

  return letters.length === 0 ? "#" : letters.slice(0, 2).join("");
}

export function looksLikeNumber(q: string): boolean {
  const compact = q.trim().replace(/[\s().-]/gu, "");
  if (!NUMBER_PATTERN.test(compact)) {
    return false;
  }
  const digitCount = compact.replace("+", "").length;

  return digitCount >= MIN_NUMBER_DIGITS && digitCount <= MAX_NUMBER_DIGITS;
}

export function relativeTimeOf(iso: string, now: Date, timezone: string | undefined): string {
  const diffMs = now.getTime() - new Date(iso).getTime();

  if (diffMs < MINUTE_MS) {
    return "now";
  }
  if (diffMs < HOUR_MS) {
    return `${String(Math.floor(diffMs / MINUTE_MS))}m`;
  }
  if (diffMs < DAY_MS) {
    return `${String(Math.floor(diffMs / HOUR_MS))}h`;
  }
  if (diffMs < WEEK_MS) {
    return `${String(Math.floor(diffMs / DAY_MS))}d`;
  }

  return dateTimeIn(iso, timezone, "short");
}
