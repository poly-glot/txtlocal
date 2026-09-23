import type { Campaign, CampaignStatus } from "@/api/generated/dashboard";

import type { StatusDisplay } from "../rules";

export const STATUS_DISPLAY: Record<CampaignStatus, StatusDisplay> = {
  CANCELLED: { label: "Cancelled", tone: "neutral" },
  DRAFT: { label: "Draft", tone: "neutral" },
  FAILED: { label: "Failed", tone: "danger" },
  SCHEDULED: { label: "Scheduled", tone: "accent" },
  SENDING: { label: "Sending", tone: "warning" },
  SENT: { label: "Sent", tone: "success" },
};

export function whenOf(campaign: Campaign): string {
  return campaign.scheduledAt ?? campaign.createdAt;
}
