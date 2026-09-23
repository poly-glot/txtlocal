import type { Product, paths } from "@/api/generated/dashboard";

import { countryNameOf } from "../rules";

type ReportingQuery = NonNullable<
  paths["/api/app/analytics/reporting"]["get"]["parameters"]["query"]
>;

const REGIONAL_INDICATOR_OFFSET = 127_397;

export interface ReportingFilterState {
  countries: string;
  products: Product | "";
  senderIds: string;
  since: string;
  until: string;
  userIds: string;
}

export function formatDay(day: string): string {
  const [year, month, date] = day.split("-");

  return `${date ?? ""}/${month ?? ""}/${year ?? ""}`;
}

export function countryFlag(iso: string): string {
  return Array.from(iso.toUpperCase(), (letter) =>
    String.fromCodePoint((letter.codePointAt(0) ?? 0) + REGIONAL_INDICATOR_OFFSET),
  ).join("");
}

export function countryLabel(iso: string): string {
  const name = countryNameOf(iso);

  return name === undefined ? iso : `${countryFlag(iso)} ${name}`;
}

function isoDate(date: Date): string {
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");

  return `${String(date.getFullYear())}-${month}-${day}`;
}

export function defaultReportingRange(now: Date): { since: string; until: string } {
  const since = new Date(now.getFullYear(), now.getMonth() - 2, 1);

  return { since: isoDate(since), until: isoDate(now) };
}

export function reportingFilterQuery(filters: ReportingFilterState): ReportingQuery {
  return {
    countries: filters.countries === "" ? [] : [filters.countries],
    products: filters.products === "" ? [] : [filters.products],
    senderIds: filters.senderIds === "" ? [] : [filters.senderIds],
    since: filters.since,
    until: filters.until,
    userIds: filters.userIds === "" ? [] : [filters.userIds],
  };
}

export function reportingQueryOf(
  filters: ReportingFilterState,
  page: number,
  pageSize: number,
): ReportingQuery {
  return { ...reportingFilterQuery(filters), page, pageSize };
}
