import { act, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { QuickSendRequest } from "@/api/generated/dashboard";
import { fakeFetch } from "@/test/fakeFetch";
import type { FakeFetch } from "@/test/fakeFetch";
import { SCHEDULED } from "@/test/fixtures/campaigns";
import { ME } from "@/test/fixtures/identity";
import { SEND_RESULT } from "@/test/fixtures/messaging";
import { renderHookWithProviders } from "@/test/render";

import { useApiMutation, useApiQuery } from "./queries";

const CAMPAIGN = { params: { path: { campaignId: SCHEDULED.campaignId } } };
const REQUEST: QuickSendRequest = {
  body: "Hello",
  kind: "SMS",
  messageType: "PROMOTIONAL",
  shortenUrls: false,
  subject: "",
  to: ["+447700900105"],
};

const balanceReads = (fetcher: FakeFetch) =>
  fetcher.calls.filter((call) => call.path === "/api/app/me").length;

describe("the invalidation table", () => {
  it("refreshes the balance after a quick send", async () => {
    const fetcher = fakeFetch({
      "GET /api/app/me": ME,
      "POST /api/app/messages/send": SEND_RESULT,
    });
    const { result } = renderHookWithProviders(
      () => ({
        me: useApiQuery("get", "/api/app/me"),
        send: useApiMutation("post", "/api/app/messages/send"),
      }),
      { fetcher },
    );
    await waitFor(() => {
      expect(result.current.me.isSuccess).toBe(true);
    });

    await act(() => result.current.send.mutateAsync({ body: REQUEST }));

    await waitFor(() => {
      expect(balanceReads(fetcher)).toBe(2);
    });
  });

  it("refreshes the balance after scheduling a campaign", async () => {
    const fetcher = fakeFetch({
      [`POST /api/app/campaigns/${SCHEDULED.campaignId}/schedule`]: SCHEDULED,
      "GET /api/app/me": ME,
    });
    const { result } = renderHookWithProviders(
      () => ({
        me: useApiQuery("get", "/api/app/me"),
        schedule: useApiMutation("post", "/api/app/campaigns/{campaignId}/schedule"),
      }),
      { fetcher },
    );
    await waitFor(() => {
      expect(result.current.me.isSuccess).toBe(true);
    });

    await act(() => result.current.schedule.mutateAsync({ ...CAMPAIGN, body: { now: true } }));

    await waitFor(() => {
      expect(balanceReads(fetcher)).toBe(2);
    });
  });

  it("refreshes the balance after cancelling a campaign", async () => {
    const fetcher = fakeFetch({
      [`POST /api/app/campaigns/${SCHEDULED.campaignId}/cancel`]: SCHEDULED,
      "GET /api/app/me": ME,
    });
    const { result } = renderHookWithProviders(
      () => ({
        cancel: useApiMutation("post", "/api/app/campaigns/{campaignId}/cancel"),
        me: useApiQuery("get", "/api/app/me"),
      }),
      { fetcher },
    );
    await waitFor(() => {
      expect(result.current.me.isSuccess).toBe(true);
    });

    await act(() => result.current.cancel.mutateAsync(CAMPAIGN));

    await waitFor(() => {
      expect(balanceReads(fetcher)).toBe(2);
    });
  });
});
