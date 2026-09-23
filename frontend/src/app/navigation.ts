import type { IconName } from "@/components/Icon/Icon";
import { API_CREDENTIALS_PATH, API_DOCS_PATH, BILLING_PATH } from "@/lib/paths";

export interface NavLeaf {
  excluded?: true;
  label: string;
  ownerOnly?: true;
  path: string;
}

interface NavTop {
  icon: IconName;
  startsSection?: true;
}

export interface NavGroup extends NavTop {
  children: readonly NavLeaf[];
  label: string;
}

export type NavEntry = NavGroup | (NavLeaf & NavTop);

export const SIDEBAR: readonly NavEntry[] = [
  { icon: "home", label: "Home", path: "/" },
  { excluded: true, icon: "automation", label: "Automation", path: "/automation" },
  { icon: "contacts", label: "Contacts", path: "/contacts" },
  {
    children: [
      { label: "Manage Senders", path: "/senders" },
      { label: "Buy A Number", path: "/senders/buy" },
    ],
    icon: "hash",
    label: "Sender IDs",
  },
  {
    children: [
      { label: "Quick SMS", path: "/sms/quick" },
      { label: "SMS Campaign", path: "/sms/campaigns" },
      { label: "Website Registration", path: "/sms/websites" },
      { label: "Templates", path: "/sms/templates" },
      { label: "Email SMS", path: "/sms/email" },
      { label: "Messenger", path: "/inbox" },
      { label: "History", path: "/sms/history" },
    ],
    icon: "message",
    label: "SMS",
  },
  {
    children: [
      { label: "Quick MMS", path: "/mms/quick" },
      { label: "MMS Campaign", path: "/mms/campaigns" },
      { label: "History", path: "/mms/history" },
    ],
    icon: "image",
    label: "MMS",
  },
  {
    excluded: true,
    icon: "link",
    label: "Integrations",
    path: "/integrations",
    startsSection: true,
  },
  {
    children: [
      { label: "API Credentials", path: API_CREDENTIALS_PATH },
      { label: "API Logs", path: "/developer/logs" },
      { label: "API Documentation", path: API_DOCS_PATH },
      { label: "Libraries & SDKs", path: API_DOCS_PATH },
      { label: "Webhooks", path: "/developer/webhooks" },
    ],
    icon: "code",
    label: "Developers",
  },
];

export const AVATAR_MENU: readonly NavLeaf[] = [
  { label: "My Profile", path: "/profile" },
  { label: "Account Settings", path: "/account" },
  { label: "Messaging Settings", path: "/account/messaging" },
  { label: "Billing", ownerOnly: true, path: BILLING_PATH },
  { label: "Global Sending", path: "/account" },
  { excluded: true, label: "Reseller Clients", path: "/reseller/clients" },
  { excluded: true, label: "Reseller Settings", path: "/reseller/settings" },
  { excluded: true, label: "Referrals", path: "/referrals" },
];

export function isGroup(entry: NavEntry): entry is NavGroup {
  return "children" in entry;
}

export function leavesOf(entries: readonly NavEntry[]): NavLeaf[] {
  return entries.flatMap((entry) => (isGroup(entry) ? entry.children : [entry]));
}
