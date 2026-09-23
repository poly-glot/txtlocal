import type { paths } from "@/api/generated/dashboard";
import type { Tone } from "@/components/Badge/Badge";
import type { Option } from "@/components/Select/Select";

const ALL_ENDPOINTS_LABEL = "All endpoints";

const WEEK_MS = 7 * 24 * 60 * 60 * 1000;

type LogsQuery = NonNullable<paths["/api/app/developer/logs"]["get"]["parameters"]["query"]>;

type StatusFilter = "All" | "Failed" | "Successful";
type DateRangePreset = "Custom" | "Last 24 hours" | "Last 7 days";

export interface LogsFilterState {
  customFrom: string;
  customTo: string;
  endpoint: string;
  preset: DateRangePreset;
  status: StatusFilter;
  subaccount: string;
}

interface LogsWindow {
  since: string | null;
  until: string | null;
}

export const STATUS_FILTERS: readonly StatusFilter[] = ["All", "Successful", "Failed"];
export const DATE_RANGE_PRESETS: readonly DateRangePreset[] = [
  "Last 24 hours",
  "Last 7 days",
  "Custom",
];

export const ENDPOINT_OPTIONS: readonly Option[] = [
  { label: ALL_ENDPOINTS_LABEL, value: "" },
  { label: "/api/v3/account", value: "/api/v3/account" },
  { label: "/api/v3/account/balance", value: "/api/v3/account/balance" },
  { label: "/api/v3/lists", value: "/api/v3/lists" },
  { label: "/api/v3/lists/{listId}/contacts", value: "/api/v3/lists/{listId}/contacts" },
  {
    label: "/api/v3/lists/{listId}/contacts/{contactId}",
    value: "/api/v3/lists/{listId}/contacts/{contactId}",
  },
  { label: "/api/v3/mms/send", value: "/api/v3/mms/send" },
  { label: "/api/v3/sender-ids", value: "/api/v3/sender-ids" },
  { label: "/api/v3/sms/history", value: "/api/v3/sms/history" },
  { label: "/api/v3/sms/send", value: "/api/v3/sms/send" },
  { label: "/api/v3/sms/{messageId}", value: "/api/v3/sms/{messageId}" },
  { label: "/api/v3/templates", value: "/api/v3/templates" },
];

export const INITIAL_LOGS_FILTERS: LogsFilterState = {
  customFrom: "",
  customTo: "",
  endpoint: "",
  preset: "Last 24 hours",
  status: "All",
  subaccount: "",
};

const OUTCOME_BY_STATUS: Record<StatusFilter, string | null> = {
  All: null,
  Failed: "failed",
  Successful: "ok",
};

const TONE_BY_OUTCOME: Record<string, Tone> = {
  failed: "danger",
  ok: "success",
  refused: "warning",
};
const DEFAULT_TONE: Tone = "neutral";

export function outcomeParam(status: StatusFilter): string | null {
  return OUTCOME_BY_STATUS[status];
}

export function outcomeTone(outcome: string): Tone {
  return TONE_BY_OUTCOME[outcome] ?? DEFAULT_TONE;
}

export function statusFilterOf(value: string): StatusFilter {
  return value === "Successful" || value === "Failed" ? value : "All";
}

export function dateRangePresetOf(value: string): DateRangePreset {
  return value === "Last 7 days" || value === "Custom" ? value : "Last 24 hours";
}

export function windowOf(filters: LogsFilterState, now: Date): LogsWindow {
  if (filters.preset === "Last 24 hours") {
    return { since: null, until: null };
  }
  if (filters.preset === "Last 7 days") {
    return { since: new Date(now.getTime() - WEEK_MS).toISOString(), until: now.toISOString() };
  }

  return {
    since: filters.customFrom === "" ? null : new Date(filters.customFrom).toISOString(),
    until: filters.customTo === "" ? null : new Date(filters.customTo).toISOString(),
  };
}

export function logsQueryOf(filters: LogsFilterState, now: Date): LogsQuery {
  const window = windowOf(filters, now);

  return {
    endpoint: filters.endpoint === "" ? null : filters.endpoint,
    outcome: outcomeParam(filters.status),
    since: window.since,
    subaccount: filters.subaccount.trim() === "" ? null : filters.subaccount.trim(),
    until: window.until,
  };
}
