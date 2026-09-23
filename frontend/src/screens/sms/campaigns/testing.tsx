import { screen } from "@testing-library/react";
import type userEvent from "@testing-library/user-event";

import { fakeFetch } from "@/test/fakeFetch";
import type { FakeFetch } from "@/test/fakeFetch";
import { DRAFT, QUOTE, REPORT, SCHEDULED } from "@/test/fixtures/campaigns";
import { EXAMPLE_LIST, OPT_OUT_LIST } from "@/test/fixtures/contacts";
import { ACCOUNT_SETTINGS } from "@/test/fixtures/identity";
import { OVERVIEW } from "@/test/fixtures/senders";
import { renderWithProviders } from "@/test/render";

import type { ScreenProduct } from "../rules";
import { CampaignsScreen } from "./CampaignsScreen";

export function renderCampaigns(
  routes: Record<string, unknown> = {},
  product: ScreenProduct = "SMS",
): FakeFetch {
  const fetcher = fakeFetch({
    "DELETE /api/app/campaigns/campaign-1": new Response(null, { status: 204 }),
    "GET /api/app/account/settings": ACCOUNT_SETTINGS,
    [`GET /api/app/campaigns?kind=${product}`]: { cursor: null, items: [SCHEDULED] },
    "GET /api/app/campaigns/campaign-1": DRAFT,
    "GET /api/app/campaigns/campaign-3/report": REPORT,
    "GET /api/app/lists": [EXAMPLE_LIST, OPT_OUT_LIST],
    "GET /api/app/senders": OVERVIEW,
    "GET /api/app/templates": [],
    "POST /api/app/campaigns": DRAFT,
    "POST /api/app/campaigns/campaign-1/quote": QUOTE,
    "POST /api/app/campaigns/campaign-1/schedule": SCHEDULED,
    "POST /api/app/campaigns/campaign-2/cancel": { ...SCHEDULED, status: "CANCELLED" },
    "POST /api/app/campaigns/campaign-2/duplicate": DRAFT,
    ...routes,
  });
  renderWithProviders(<CampaignsScreen product={product} />, { fetcher });

  return fetcher;
}

export async function openEditor(user: ReturnType<typeof userEvent.setup>): Promise<void> {
  await user.click(await screen.findByRole("button", { name: "Add campaign" }));
  await screen.findByRole("region", { name: "Message" });
}

export async function composeCampaign(user: ReturnType<typeof userEvent.setup>): Promise<void> {
  await openEditor(user);
  await user.type(screen.getByLabelText("Campaign name"), "Helloworld");
  await user.selectOptions(screen.getByLabelText("List"), EXAMPLE_LIST.listId);
  await user.type(screen.getByLabelText("Your SMS Content"), "Hello");
  await user.click(screen.getByRole("button", { name: "NEXT" }));
}
