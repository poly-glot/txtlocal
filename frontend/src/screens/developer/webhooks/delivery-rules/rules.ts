import type {
  DeliveryEventsFilter,
  DeliveryReportRuleRequest,
  DeliveryReportRuleView,
} from "@/api/generated/dashboard";
import type { Option } from "@/components/Select/Select";

import type { RuleEdit } from "../rules";

const HTTPS_PREFIX = "https://";

export interface DeliveryRuleDraft {
  enabled: boolean;
  events: DeliveryEventsFilter;
  name: string;
  url: string;
}

export const DELIVERY_EVENT_OPTIONS: readonly Option[] = [
  { label: "All", value: "ALL" },
  { label: "Delivered only", value: "DELIVERED" },
  { label: "Failed only", value: "FAILED" },
];

export const EMPTY_DELIVERY_DRAFT: DeliveryRuleDraft = {
  enabled: true,
  events: "ALL",
  name: "",
  url: "",
};

const DELIVERY_EVENT_VALUES = new Set(DELIVERY_EVENT_OPTIONS.map((option) => option.value));

export function isDeliveryEvents(value: string): value is DeliveryEventsFilter {
  return DELIVERY_EVENT_VALUES.has(value);
}

export function draftOfDeliveryRule(rule: DeliveryReportRuleView): DeliveryRuleDraft {
  return { enabled: rule.enabled, events: rule.events, name: rule.name, url: rule.url };
}

export function deliveryRuleRequestOf(draft: DeliveryRuleDraft): DeliveryReportRuleRequest {
  return { enabled: draft.enabled, events: draft.events, name: draft.name, url: draft.url };
}

export function toggledDeliveryRule(
  rule: DeliveryReportRuleView,
): RuleEdit<DeliveryReportRuleRequest> {
  return {
    input: deliveryRuleRequestOf({ ...draftOfDeliveryRule(rule), enabled: !rule.enabled }),
    ruleId: rule.ruleId,
  };
}

export function isHttpsUrl(url: string): boolean {
  return url.startsWith(HTTPS_PREFIX) && url.length > HTTPS_PREFIX.length;
}

export function isDeliveryRuleSaveable(draft: DeliveryRuleDraft): boolean {
  return draft.name.trim() !== "" && isHttpsUrl(draft.url);
}
