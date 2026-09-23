import type { ConversationView, MessageRow, ThreadPage } from "@/api/generated/dashboard";

import { ME, OWNER_ROW } from "./identity";
import { OWN_SENDER } from "./senders";

export const JANE_PEER = "+447400123123";

export const JANE_CONVERSATION: ConversationView = {
  lastAt: "2026-09-19T11:50:00Z",
  lastDirection: "IN",
  lastPreview: "Hey, are we still on for tomorrow?",
  lastSenderId: OWN_SENDER.senderId,
  name: "Jane Austen",
  peer: JANE_PEER,
  status: "OPEN",
  unread: 2,
};

const MESSAGE_BASE = {
  accountId: ME.accountId,
  campaignId: "campaign-1",
  country: "GB",
  encoding: "GSM7",
  kind: "SMS",
  parts: 1,
  senderId: OWN_SENDER.senderId,
} as const;

export const JANE_MESSAGES: MessageRow[] = [
  {
    ...MESSAGE_BASE,
    body: "Hey, are we still on for tomorrow?",
    direction: "IN",
    from: JANE_PEER,
    messageId: "message-2",
    priceMicro: 0,
    queuedAt: "2026-09-19T11:50:00Z",
    status: "RECEIVED",
    to: OWN_SENDER.senderId,
    userId: "system",
    username: "inbox",
  },
  {
    ...MESSAGE_BASE,
    body: "Yes, see you at 10.",
    direction: "OUT",
    from: OWN_SENDER.senderId,
    messageId: "message-1",
    priceMicro: 3200,
    queuedAt: "2026-09-19T09:00:00Z",
    status: "DELIVERED",
    to: JANE_PEER,
    userId: OWNER_ROW.userId,
    username: "owner",
  },
];

export const JANE_THREAD: ThreadPage = {
  conversation: JANE_CONVERSATION,
  messages: { items: JANE_MESSAGES, nextCursor: null },
  replyHint: "Replies to this number reach you only when the contact replies to your last message",
};
