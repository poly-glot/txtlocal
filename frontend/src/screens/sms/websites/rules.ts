import type { WebsiteStatus, WebsitesRequest } from "@/api/generated/dashboard";

import type { StatusDisplay } from "../rules";

export const MAX_WEBSITES_PER_SUBMISSION = 3;

export const WEBSITE_STATUS_DISPLAY: Record<WebsiteStatus, StatusDisplay> = {
  APPROVED: { label: "Approved", tone: "success" },
  REJECTED: { label: "Rejected", tone: "danger" },
  UNDER_REVIEW: { label: "Under review", tone: "warning" },
};

const HOSTNAME_RE = /^(?!-)[a-z0-9-]{1,63}(?<!-)(\.(?!-)[a-z0-9-]{1,63}(?<!-))*\.[a-z]{2,}$/;

export function normaliseDomain(raw: string): string {
  const withoutScheme = raw
    .trim()
    .toLowerCase()
    .replace(/^[a-z][a-z0-9+.-]*:\/\//, "");
  const host = withoutScheme.split(/[/?#]/)[0] ?? "";

  return host.replace(/\.$/, "");
}

export function isValidDomain(domain: string): boolean {
  return HOSTNAME_RE.test(domain);
}

export function hasRegisterableDomain(domains: readonly string[]): boolean {
  return domains.some((domain) => isValidDomain(normaliseDomain(domain)));
}

export function websitesRequestOf(domains: readonly string[]): WebsitesRequest {
  return { domains: domains.map(normaliseDomain).filter((domain) => domain !== "") };
}

export function withDomainRow(domains: readonly string[]): string[] {
  return domains.length >= MAX_WEBSITES_PER_SUBMISSION ? [...domains] : [...domains, ""];
}

export function withoutDomainRow(domains: readonly string[], index: number): string[] {
  return domains.filter((_, rowIndex) => rowIndex !== index);
}

export function withDomainAt(domains: readonly string[], index: number, value: string): string[] {
  return domains.map((domain, rowIndex) => (rowIndex === index ? value : domain));
}

export function registeredDateDisplay(iso: string): string {
  return new Intl.DateTimeFormat("en-GB", {
    day: "numeric",
    month: "long",
    year: "numeric",
  }).format(new Date(iso));
}
