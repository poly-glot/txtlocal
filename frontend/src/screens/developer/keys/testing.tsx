import { screen, within } from "@testing-library/react";
import type userEvent from "@testing-library/user-event";

import { fakeFetch } from "@/test/fakeFetch";
import type { FakeFetch } from "@/test/fakeFetch";
import { GENERAL } from "@/test/fixtures/developer";
import { ACCOUNT_USERS, CREATED_SUBACCOUNT } from "@/test/fixtures/identity";
import { renderWithProviders } from "@/test/render";

import { ApiGeneralTab } from "./ApiGeneralTab";
import { SubaccountsTab } from "./SubaccountsTab";

export function renderApiGeneralTab(routes: Record<string, unknown> = {}): FakeFetch {
  const fetcher = fakeFetch({ "GET /api/app/developer/general": GENERAL, ...routes });
  renderWithProviders(<ApiGeneralTab />, { fetcher });

  return fetcher;
}

export function renderSubaccounts(routes: Record<string, unknown> = {}): FakeFetch {
  const fetcher = fakeFetch({
    "GET /api/app/account/users": ACCOUNT_USERS,
    "POST /api/app/account/users": CREATED_SUBACCOUNT,
    ...routes,
  });
  renderWithProviders(<SubaccountsTab />, { fetcher });

  return fetcher;
}

export async function addSubaccount(user: ReturnType<typeof userEvent.setup>): Promise<void> {
  await user.click(await screen.findByRole("button", { name: "ADD SUBACCOUNT" }));
  const dialog = screen.getByRole("dialog", { name: "Add subaccount" });
  await user.type(within(dialog).getByLabelText("Username / Email"), "new@txtlocal.local");
  await user.type(within(dialog).getByLabelText("First Name"), "Sam");
  await user.click(within(dialog).getByRole("button", { name: "ADD" }));
}
