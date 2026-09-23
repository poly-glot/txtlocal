import type {
  DeliveryReportRuleView,
  EmailSender,
  InboundRule,
  Website,
} from "@/api/generated/dashboard";

import { OPT_OUT_LIST_ID } from "./contacts";
import { OWNER_ROW } from "./identity";
import { SHARED_SENDER } from "./senders";

export const DEFAULT_RULE: InboundRule = {
  action: "EMAIL_USER",
  actionAddress: null,
  backupEmail: null,
  createdAt: "2026-09-19T10:00:00Z",
  enabled: true,
  keyword: null,
  matchKind: "ANY",
  name: "Default rule",
  number: null,
  ruleId: "rule-default",
  secret: null,
};

export const OPT_OUT_RULE: InboundRule = {
  action: "MOVE_CONTACT",
  actionAddress: OPT_OUT_LIST_ID,
  backupEmail: null,
  createdAt: "2026-09-19T10:00:00Z",
  enabled: true,
  keyword: "stop",
  matchKind: "KEYWORD",
  name: "Opt-out contact",
  number: null,
  ruleId: "rule-opt-out",
  secret: null,
};

export const DELIVERY_RULE: DeliveryReportRuleView = {
  createdAt: "2026-09-19T10:00:00Z",
  enabled: true,
  events: "ALL",
  name: "Order updates",
  ruleId: "delivery-1",
  url: "https://example.com/webhook",
};

export const WEBSITE: Website = {
  domain: "junaid.guru",
  registeredAt: "2026-09-19T10:00:00Z",
  status: "UNDER_REVIEW",
};

export const EMAIL_SENDER: EmailSender = {
  email: "sales@txtlocal.local",
  senderId: SHARED_SENDER.senderId,
  userId: OWNER_ROW.userId,
};
