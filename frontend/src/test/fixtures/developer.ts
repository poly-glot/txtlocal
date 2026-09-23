import type { DeveloperGeneral, LogRow, LogsPage } from "@/api/generated/dashboard";
import type { OpenApiDocument } from "@/screens/developer/docs/rules";

import { OWNER_ROW } from "./identity";

export const GENERAL: DeveloperGeneral = {
  baseUrl: "https://api.txtlocal.local",
  docsUrl: "https://docs.txtlocal.local",
  rateLimitPerMinute: 60,
};

export const OK_ROW: LogRow = {
  latencyMs: 120,
  method: "POST",
  outcome: "ok",
  requestId: "req-1",
  route: "/api/v3/sms/send",
  status: 201,
  timestamp: "2026-09-19T14:13:44Z",
  userId: OWNER_ROW.userId,
};

export const FAILED_ROW: LogRow = {
  ...OK_ROW,
  latencyMs: 340,
  method: "GET",
  outcome: "failed",
  requestId: "req-2",
  route: "/api/v3/sms/history",
  status: 500,
};

export const LOGS: LogsPage = {
  resultsPerPage: 20,
  rows: [OK_ROW, FAILED_ROW],
  tiles: { failed: 1, successful: 1, total: 2 },
};

export const OPENAPI_FIXTURE: OpenApiDocument = {
  components: {
    schemas: {
      V3Balance: {
        properties: {
          balance: { title: "Balance", type: "string" },
          currency: { title: "Currency", type: "string" },
        },
        required: ["balance", "currency"],
        title: "V3Balance",
        type: "object",
      },
      V3ListRequest: {
        properties: { name: { title: "Name", type: "string" } },
        required: ["name"],
        title: "V3ListRequest",
        type: "object",
      },
    },
  },
  paths: {
    "/api/v3/account/balance": {
      get: {
        responses: {
          "200": {
            content: { "application/json": { schema: { $ref: "#/components/schemas/V3Balance" } } },
          },
        },
        summary: "Balance",
      },
    },
    "/api/v3/lists": {
      post: {
        requestBody: {
          content: {
            "application/json": { schema: { $ref: "#/components/schemas/V3ListRequest" } },
          },
        },
        responses: { "201": { content: { "application/json": { schema: {} } } } },
        summary: "Create List",
      },
    },
  },
};
