import type { Campaign, CampaignQuote, CampaignReport } from "@/api/generated/dashboard";

import { EXAMPLE_LIST_ID } from "./contacts";
import { OWNER_ROW } from "./identity";
import { SHARED_SENDER } from "./senders";

export const DRAFT: Campaign = {
  body: "Hello {first_name}",
  campaignId: "campaign-1",
  channel: "SMS",
  counts: { delivered: 0, queued: 0, recipients: 0, refused: 0, sent: 0, undelivered: 0 },
  createdAt: "2026-09-19T10:00:00Z",
  footer: "Reply STOP to opt-out",
  kind: "LIST",
  listId: EXAMPLE_LIST_ID,
  name: "Helloworld",
  optOutMode: "REPLY_STOP",
  quoteMicro: 0,
  recipients: [],
  reservedMicro: 0,
  senderId: SHARED_SENDER.senderId,
  shortenUrls: false,
  status: "DRAFT",
  userId: OWNER_ROW.userId,
  username: "demo@txtlocal.local",
};

export const SCHEDULED: Campaign = {
  ...DRAFT,
  campaignId: "campaign-2",
  counts: { delivered: 0, queued: 0, recipients: 1, refused: 0, sent: 0, undelivered: 0 },
  name: "Summer sale",
  scheduledAt: "2027-07-31T22:59:00Z",
  status: "SCHEDULED",
};

export const SENT: Campaign = {
  ...DRAFT,
  campaignId: "campaign-3",
  counts: { delivered: 1, queued: 2, recipients: 2, refused: 0, sent: 2, undelivered: 1 },
  kind: "QUICK",
  name: "Quick SMS 19 Sep 2026 14:13",
  status: "SENT",
};

export const QUOTE: CampaignQuote = {
  costMicro: 85_400,
  parts: 1,
  recipients: 2,
  senderDisplay: "Shared Number",
};

export const REPORT: CampaignReport = { campaign: SENT, clicks: 0 };
