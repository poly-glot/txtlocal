export const BILLING_TABS = [
  { label: "Top Up Account", slug: "top-up" },
  { label: "Manage Credit Cards", slug: "cards" },
  { label: "Transactions", slug: "transactions" },
  { label: "Usage", slug: "usage" },
  { label: "Usage Reporting", slug: "usage-reporting" },
  { label: "General", slug: "general" },
  { label: "Upcoming Charges", slug: "upcoming-charges" },
] as const;

export type BillingSlug = (typeof BILLING_TABS)[number]["slug"];
