import { fakeFetch } from "@/test/fakeFetch";
import type { FakeFetch } from "@/test/fakeFetch";
import {
  ALEX,
  CONTACTS_PATH,
  EXAMPLE_LIST,
  OPT_OUT_CONTACTS_PATH,
  OPT_OUT_LIST,
  SAM,
} from "@/test/fixtures/contacts";
import { ACCOUNT_SETTINGS } from "@/test/fixtures/identity";
import { renderWithProviders } from "@/test/render";

import { ContactsScreen } from "./ContactsScreen";

export function renderContacts(routes: Record<string, unknown> = {}): FakeFetch {
  const fetcher = fakeFetch({
    "GET /api/app/account/settings": ACCOUNT_SETTINGS,
    "GET /api/app/lists": [EXAMPLE_LIST, OPT_OUT_LIST],
    [`GET ${CONTACTS_PATH}?limit=20`]: { cursor: null, items: [SAM, ALEX] },
    [`GET ${OPT_OUT_CONTACTS_PATH}?limit=20`]: { cursor: null, items: [] },
    ...routes,
  });
  renderWithProviders(<ContactsScreen />, { fetcher });

  return fetcher;
}
