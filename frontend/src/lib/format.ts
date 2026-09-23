import type { Result } from "@/types";

export type DateStyle = "medium" | "short";

export function dataOf<T>(result: Result<T> | undefined, fallback: T): T {
  return result?.status === "OK" ? result.data : fallback;
}

export function dateTimeIn(
  iso: string,
  timezone: string | undefined,
  dateStyle: DateStyle,
): string {
  const format = new Intl.DateTimeFormat("en-GB", {
    dateStyle,
    timeStyle: "short",
    timeZone: timezone,
  });

  return format.format(new Date(iso));
}

export function minuteValue(date: Date): string {
  const year = String(date.getFullYear());
  const day = `${padded(date.getMonth() + 1)}-${padded(date.getDate())}`;
  const time = `${padded(date.getHours())}:${padded(date.getMinutes())}`;

  return `${year}-${day}T${time}`;
}

function padded(part: number): string {
  return String(part).padStart(2, "0");
}
