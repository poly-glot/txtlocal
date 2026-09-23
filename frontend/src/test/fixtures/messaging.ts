import type {
  ContactHit,
  HistoryPage,
  MessageRow,
  QuickQuote,
  QuickSendResult,
  Template,
} from "@/api/generated/dashboard";

import { EXAMPLE_LIST_ID } from "./contacts";
import { ME, OWNER_ROW } from "./identity";
import { SHARED_SENDER } from "./senders";

export const SEND_RESULT: QuickSendResult = {
  campaignId: "c-1",
  costMicro: 42_700,
  recipients: 1,
  refused: [],
};

export const CONTACT_HIT: ContactHit = {
  firstName: "Sam",
  lastName: "Patel",
  listId: EXAMPLE_LIST_ID,
  mobile: "+447400123105",
};

export const QUOTE: QuickQuote = { costMicro: 85_400, parts: 1, recipients: 2, refused: [] };

export const DELIVERED_ROW: MessageRow = {
  accountId: ME.accountId,
  body: "Hello from the local build",
  campaignId: "campaign-1",
  country: "GB",
  deliveredAt: "2026-09-19T14:13:44Z",
  direction: "OUT",
  encoding: "GSM7",
  failureReason: null,
  from: "SHARED",
  kind: "SMS",
  messageId: "message-1",
  parts: 1,
  priceMicro: 42_700,
  providerMessageId: "fake-1",
  queuedAt: "2026-09-19T14:13:44Z",
  senderId: SHARED_SENDER.senderId,
  sentAt: "2026-09-19T14:13:44Z",
  status: "DELIVERED",
  to: "+447400123105",
  userId: OWNER_ROW.userId,
  username: "demo@txtlocal.local",
};

export const FAILED_ROW: MessageRow = {
  ...DELIVERED_ROW,
  deliveredAt: null,
  failureReason: "The handset rejected the message",
  messageId: "message-2",
  status: "FAILED",
  to: "+447400123100",
};

export const HISTORY: HistoryPage = { cursor: null, items: [DELIVERED_ROW, FAILED_ROW] };

export const TEMPLATE: Template = {
  body: "Hello {first_name}",
  createdAt: "2026-09-19T10:00:00Z",
  name: "Welcome",
  templateId: "template-1",
};
