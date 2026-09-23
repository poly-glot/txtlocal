import type { CampaignDraft, ContactList } from "@/api/generated/dashboard";
import { segmentSummary, segmentsOf } from "@/rules/segments";

import type { ScreenProduct } from "../../../rules";
import { REPLY_STOP_FOOTER } from "../rules";

const MMS_COUNTER = "1 MMS per recipient.";

const OPT_OUT_LIST_KIND = "OPT_OUT";

const UNSUBSCRIBE_FOOTER = "Unsubscribe: {unsubscribe_link}";

export type OptOutMode = CampaignDraft["optOutMode"];

export function contentTitle(product: ScreenProduct): string {
  return `Your ${product} Content`;
}

export function counterText(draft: CampaignDraft, product: ScreenProduct): string {
  if (product === "MMS") {
    return MMS_COUNTER;
  }

  return segmentSummary(segmentsOf(withFooter(draft.body, draft.footer)));
}

export function footerFor(mode: OptOutMode): string {
  return mode === "REPLY_STOP" ? REPLY_STOP_FOOTER : UNSUBSCRIBE_FOOTER;
}

export function isMessageComplete(draft: CampaignDraft, product: ScreenProduct): boolean {
  return product === "MMS" ? draft.mediaKey !== null : draft.body.trim() !== "";
}

export function listSummary(list: ContactList): string {
  return `${list.name} ${String(list.contactCount)} recipient(s)`;
}

export function senderTitle(product: ScreenProduct): string {
  return product === "MMS" ? "Your Sender Details" : "Select your Sender ID";
}

export function sendableLists(lists: readonly ContactList[]): ContactList[] {
  return lists.filter((list) => list.kind !== OPT_OUT_LIST_KIND);
}

function withFooter(body: string, footer: string): string {
  return footer === "" ? body : `${body}\n${footer}`;
}
