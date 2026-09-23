import type {
  ContactList,
  InboundRule,
  InboundRuleRequest,
  MatchKind,
  RuleAction,
  SenderView,
  SendersView,
} from "@/api/generated/dashboard";
import type { Option } from "@/components/Select/Select";

import type { RuleEdit } from "../rules";

const BACKUP_EMAIL_HELPER =
  "This email will be forwarded to only in case account user email cannot be found.";

const NO_MATCH = "—";

export type ActionFieldKind = "email" | "list" | "text" | "textarea" | "url";

export interface ActionField {
  helper?: string;
  kind: ActionFieldKind;
  label: string;
  required: boolean;
  target: "actionAddress" | "backupEmail";
}

export interface InboundRuleDraft {
  action: RuleAction;
  actionAddress: string;
  backupEmail: string;
  enabled: boolean;
  keyword: string;
  matchKind: MatchKind;
  name: string;
  number: string;
}

const ACTION_FIELDS: Record<RuleAction, ActionField | null> = {
  AUTO_REPLY: {
    kind: "textarea",
    label: "Reply message",
    required: true,
    target: "actionAddress",
  },
  EMAIL_FIXED: { kind: "email", label: "Email Address", required: true, target: "actionAddress" },
  EMAIL_USER: {
    helper: BACKUP_EMAIL_HELPER,
    kind: "email",
    label: "Back-up Email Address",
    required: false,
    target: "backupEmail",
  },
  GROUP_SMS: { kind: "list", label: "List", required: true, target: "actionAddress" },
  MOVE_CONTACT: { kind: "list", label: "List", required: true, target: "actionAddress" },
  POLL: null,
  SEND_TO_MESSENGER: null,
  SMS: { kind: "text", label: "Forward to number", required: true, target: "actionAddress" },
  URL: { kind: "url", label: "URL", required: true, target: "actionAddress" },
};

export const ACTION_OPTIONS: readonly Option[] = [
  { label: "AUTO_REPLY", value: "AUTO_REPLY" },
  { label: "EMAIL_USER", value: "EMAIL_USER" },
  { label: "EMAIL_FIXED", value: "EMAIL_FIXED" },
  { label: "URL", value: "URL" },
  { label: "SMS", value: "SMS" },
  { label: "POLL", value: "POLL" },
  { label: "GROUP_SMS", value: "GROUP_SMS" },
  { label: "MOVE_CONTACT", value: "MOVE_CONTACT" },
  { label: "SEND_TO_MESSENGER", value: "SEND_TO_MESSENGER" },
];

export const MATCH_KIND_OPTIONS: readonly Option[] = [
  { label: "Any message", value: "ANY" },
  { label: "Keyword", value: "KEYWORD" },
];

export const EMPTY_INBOUND_DRAFT: InboundRuleDraft = {
  action: "EMAIL_USER",
  actionAddress: "",
  backupEmail: "",
  enabled: true,
  keyword: "",
  matchKind: "ANY",
  name: "",
  number: "",
};

const ACTION_VALUES = new Set(ACTION_OPTIONS.map((option) => option.value));

export function isRuleAction(value: string): value is RuleAction {
  return ACTION_VALUES.has(value);
}

export function actionFieldFor(action: RuleAction): ActionField | null {
  return ACTION_FIELDS[action];
}

export function actionFieldValue(draft: InboundRuleDraft, field: ActionField): string {
  return field.target === "backupEmail" ? draft.backupEmail : draft.actionAddress;
}

export function withActionValue(
  draft: InboundRuleDraft,
  field: ActionField,
  value: string,
): InboundRuleDraft {
  return field.target === "backupEmail"
    ? { ...draft, backupEmail: value }
    : { ...draft, actionAddress: value };
}

export function draftOfInboundRule(rule: InboundRule): InboundRuleDraft {
  return {
    action: rule.action,
    actionAddress: rule.actionAddress ?? "",
    backupEmail: rule.backupEmail ?? "",
    enabled: rule.enabled,
    keyword: rule.keyword ?? "",
    matchKind: rule.matchKind,
    name: rule.name,
    number: rule.number ?? "",
  };
}

export function inboundRuleRequestOf(draft: InboundRuleDraft): InboundRuleRequest {
  return {
    action: draft.action,
    actionAddress: draft.actionAddress === "" ? null : draft.actionAddress,
    backupEmail: draft.backupEmail === "" ? null : draft.backupEmail,
    enabled: draft.enabled,
    keyword: draft.matchKind === "KEYWORD" && draft.keyword !== "" ? draft.keyword : null,
    matchKind: draft.matchKind,
    name: draft.name,
    number: draft.number === "" ? null : draft.number,
  };
}

export function toggledInboundRule(rule: InboundRule): RuleEdit<InboundRuleRequest> {
  return {
    input: inboundRuleRequestOf({ ...draftOfInboundRule(rule), enabled: !rule.enabled }),
    ruleId: rule.ruleId,
  };
}

export function isInboundRuleSaveable(draft: InboundRuleDraft): boolean {
  if (draft.name.trim() === "") {
    return false;
  }
  if (draft.matchKind === "KEYWORD" && draft.keyword.trim() === "") {
    return false;
  }

  const field = actionFieldFor(draft.action);
  if (!field?.required) {
    return true;
  }

  return actionFieldValue(draft, field).trim() !== "";
}

export function matchForDisplay(rule: InboundRule): string {
  return rule.matchKind === "KEYWORD" ? (rule.keyword ?? "") : NO_MATCH;
}

export function actionAddressDisplay(rule: InboundRule): string {
  return rule.actionAddress ?? NO_MATCH;
}

export function dedicatedNumbers(view: SendersView): SenderView[] {
  return view.senders.DEDICATED ?? [];
}

export function listOptions(lists: readonly ContactList[]): Option[] {
  return lists.map((list) => ({ label: list.name, value: list.listId }));
}

export function numberOptions(senders: readonly SenderView[]): Option[] {
  return senders.map((sender) => ({ label: sender.display, value: sender.value }));
}
