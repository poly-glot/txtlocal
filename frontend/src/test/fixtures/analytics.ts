import type { ReportingPage, UsageTabPage } from "@/api/generated/dashboard";

import { OWNER_ROW } from "./identity";

export const REPORTING_NOW = new Date(2026, 8, 19);
export const USAGE_MONTH_ROUTE = "GET /api/app/analytics/usage?month=2026-09";
export const REPORTING_ROUTE =
  "GET /api/app/analytics/reporting?page=1&pageSize=10&since=2026-07-01&until=2026-09-19";
export const REPORTING_EXPORT_PATH =
  "/api/app/analytics/reporting/export?since=2026-07-01&until=2026-09-19";

export const USAGE_PAGE: UsageTabPage = {
  rows: [
    { costMicro: 42_700, month: "2026-09", product: "SMS", quantity: 1, userId: OWNER_ROW.userId },
    {
      costMicro: 85_400,
      month: "2026-09",
      product: "MMS_AS_LINK",
      quantity: 2,
      userId: "user-2",
    },
  ],
};

export const REPORTING_PAGE: ReportingPage = {
  page: 1,
  pageSize: 10,
  rows: [
    {
      country: "GB",
      day: "2026-09-19",
      priceMicro: 42_700,
      product: "SMS",
      quantity: 1,
      senderId: "+447908661626",
      totalMicro: 42_700,
      userId: OWNER_ROW.userId,
    },
  ],
  totalResults: 1,
};
