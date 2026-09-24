import type { ComponentType } from "react";
import { Navigate } from "react-router";
import type { RouteObject } from "react-router";

import { StatusMessage } from "@/components/StatusMessage/StatusMessage";
import { API_CREDENTIALS_PATH, API_DOCS_PATH, BILLING_PATH, CALLBACK_PATH } from "@/lib/paths";
import { BillingIndexRedirect } from "@/screens/billing/BillingIndexRedirect";
import { BILLING_TABS } from "@/screens/billing/billingTabs";
import type { BillingSlug } from "@/screens/billing/billingTabs";

import { Shell } from "./shell/Shell";

type LoadScreen = () => Promise<ComponentType>;

const BILLING_SCREENS: Record<BillingSlug, LoadScreen> = {
  cards: async () => (await import("@/screens/billing/cards/CardsScreen")).CardsScreen,
  general: async () => (await import("@/screens/billing/general/GeneralScreen")).GeneralScreen,
  "top-up": async () => (await import("@/screens/billing/top-up/TopUpScreen")).TopUpScreen,
  transactions: async () =>
    (await import("@/screens/billing/transactions/TransactionsScreen")).TransactionsScreen,
  "upcoming-charges": async () =>
    (await import("@/screens/billing/upcoming-charges/UpcomingChargesScreen"))
      .UpcomingChargesScreen,
  usage: async () => (await import("@/screens/billing/usage/UsageScreen")).UsageScreen,
  "usage-reporting": async () =>
    (await import("@/screens/billing/usage-reporting/UsageReportingScreen")).UsageReportingScreen,
};

const billingTab = (tab: (typeof BILLING_TABS)[number]): RouteObject => ({
  lazy: async () => ({ Component: await BILLING_SCREENS[tab.slug]() }),
  path: tab.slug,
});

const built: RouteObject[] = [
  {
    lazy: async () => ({ Component: (await import("@/screens/home/HomeScreen")).HomeScreen }),
    path: "/",
  },
  {
    lazy: async () => ({
      Component: (await import("@/screens/contacts/ContactsScreen")).ContactsScreen,
    }),
    path: "/contacts",
  },
  {
    lazy: async () => ({
      Component: (await import("@/screens/profile/ProfileScreen")).ProfileScreen,
    }),
    path: "/profile",
  },
  {
    lazy: async () => ({
      Component: (await import("@/screens/account/AccountSettingsScreen")).AccountSettingsScreen,
    }),
    path: "/account",
  },
  {
    lazy: async () => ({
      Component: (await import("@/screens/account/messaging/MessagingSettingsScreen"))
        .MessagingSettingsScreen,
    }),
    path: "/account/messaging",
  },
  {
    lazy: async () => ({
      Component: (await import("@/screens/senders/ManageSendersScreen")).ManageSendersScreen,
    }),
    path: "/senders",
  },
  {
    lazy: async () => ({
      Component: (await import("@/screens/senders/buy/BuyANumberScreen")).BuyANumberScreen,
    }),
    path: "/senders/buy",
  },
  {
    lazy: async () => ({
      Component: (await import("@/screens/developer/keys/ApiCredentialsScreen"))
        .ApiCredentialsScreen,
    }),
    path: API_CREDENTIALS_PATH,
  },
  {
    lazy: async () => ({
      Component: (await import("@/screens/developer/logs/ApiLogsScreen")).ApiLogsScreen,
    }),
    path: "/developer/logs",
  },
  {
    lazy: async () => ({
      Component: (await import("@/screens/developer/docs/ApiDocsScreen")).ApiDocsScreen,
    }),
    path: API_DOCS_PATH,
  },
  {
    lazy: async () => ({
      Component: (await import("@/screens/developer/webhooks/WebhooksScreen")).WebhooksScreen,
    }),
    path: "/developer/webhooks",
  },
  {
    children: [
      { element: <BillingIndexRedirect />, index: true },
      ...BILLING_TABS.map(billingTab),
      { element: <BillingIndexRedirect />, path: "*" },
    ],
    lazy: async () => ({
      Component: (await import("@/screens/billing/BillingLayout")).BillingLayout,
    }),
    path: BILLING_PATH,
  },
  {
    lazy: async () => {
      const { QuickSendScreen } = await import("@/screens/sms/quick/QuickSendScreen");

      return { element: <QuickSendScreen kind="SMS" /> };
    },
    path: "/sms/quick",
  },
  {
    lazy: async () => {
      const { CampaignsScreen } = await import("@/screens/sms/campaigns/CampaignsScreen");

      return { element: <CampaignsScreen product="SMS" /> };
    },
    path: "/sms/campaigns",
  },
  {
    lazy: async () => ({
      Component: (await import("@/screens/sms/websites/WebsitesScreen")).WebsitesScreen,
    }),
    path: "/sms/websites",
  },
  {
    lazy: async () => ({
      Component: (await import("@/screens/sms/templates/TemplatesScreen")).TemplatesScreen,
    }),
    path: "/sms/templates",
  },
  {
    lazy: async () => ({
      Component: (await import("@/screens/sms/email/EmailSmsScreen")).EmailSmsScreen,
    }),
    path: "/sms/email",
  },
  {
    lazy: async () => ({ Component: (await import("@/screens/inbox/InboxScreen")).InboxScreen }),
    path: "/inbox",
  },
  {
    lazy: async () => ({
      Component: (await import("@/screens/sms/history/HistoryScreen")).HistoryScreen,
    }),
    path: "/sms/history",
  },
  {
    lazy: async () => {
      const { QuickSendScreen } = await import("@/screens/sms/quick/QuickSendScreen");

      return { element: <QuickSendScreen kind="MMS" /> };
    },
    path: "/mms/quick",
  },
  {
    lazy: async () => {
      const { CampaignsScreen } = await import("@/screens/sms/campaigns/CampaignsScreen");

      return { element: <CampaignsScreen product="MMS" /> };
    },
    path: "/mms/campaigns",
  },
  {
    lazy: async () => {
      const { HistoryScreen } = await import("@/screens/sms/history/HistoryScreen");

      return { element: <HistoryScreen product="MMS" /> };
    },
    path: "/mms/history",
  },
];

export function appRoutes(): RouteObject[] {
  return [
    {
      HydrateFallback: StatusMessage,
      lazy: async () => ({
        Component: (await import("@/screens/auth/callback/CallbackScreen")).CallbackScreen,
      }),
      path: CALLBACK_PATH,
    },
    {
      HydrateFallback: StatusMessage,
      children: [...built, { element: <Navigate replace to="/" />, path: "*" }],
      element: <Shell />,
    },
  ];
}
