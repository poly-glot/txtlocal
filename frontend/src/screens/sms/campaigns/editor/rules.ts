import type { Campaign, CampaignDraft, ScheduleRequest } from "@/api/generated/dashboard";

import type { ScreenProduct } from "../../rules";
import { NOW_LABEL } from "../../rules";

const DAY_MS = 86_400_000;
const HOUR_MS = 3_600_000;
const MONTH_MS = 2_629_800_000;

export const REPLY_STOP_FOOTER = "Reply STOP to opt-out";

const MINUTE_MS = 60_000;
const MINUTE_STEP = { ms: MINUTE_MS, unit: "minute" } as const;
const RELATIVE_STEPS = [
  { ms: MONTH_MS, unit: "month" },
  { ms: DAY_MS, unit: "day" },
  { ms: HOUR_MS, unit: "hour" },
  MINUTE_STEP,
] as const;

export function draftOf(campaign: Campaign | undefined, product: ScreenProduct): CampaignDraft {
  if (campaign === undefined) {
    return emptyDraft(product);
  }

  return {
    body: campaign.body,
    footer: campaign.footer,
    listId: campaign.listId ?? null,
    mediaKey: campaign.mediaKey ?? null,
    name: campaign.name,
    optOutMode: campaign.optOutMode,
    product: campaign.channel,
    senderId: campaign.senderId,
    shortenUrls: campaign.shortenUrls,
    subject: campaign.subject ?? null,
  };
}

export function emptyDraft(product: ScreenProduct): CampaignDraft {
  return {
    body: "",
    footer: REPLY_STOP_FOOTER,
    listId: null,
    mediaKey: null,
    name: "",
    optOutMode: "REPLY_STOP",
    product,
    senderId: "",
    shortenUrls: false,
    subject: null,
  };
}

export function scheduleLabel(sendAt: string, now: Date, timezone: string | undefined): string {
  if (sendAt === "") {
    return NOW_LABEL;
  }

  const when = new Date(sendAt);

  return `${dayIn(when, timezone)} (${relativeLabel(when, now)})`;
}

export function scheduleRequestOf(sendAt: string): ScheduleRequest {
  return sendAt === "" ? { now: true } : { now: false, sendAt: new Date(sendAt).toISOString() };
}

function dayIn(date: Date, timezone: string | undefined): string {
  const format = new Intl.DateTimeFormat("en-GB", {
    day: "numeric",
    month: "short",
    timeZone: timezone,
    year: "numeric",
  });

  return format.format(date);
}

function relativeLabel(target: Date, now: Date): string {
  const delta = target.getTime() - now.getTime();
  const step = RELATIVE_STEPS.find((candidate) => Math.abs(delta) >= candidate.ms) ?? MINUTE_STEP;
  const format = new Intl.RelativeTimeFormat("en-GB", { numeric: "auto" });

  return format.format(Math.round(delta / step.ms), step.unit);
}
