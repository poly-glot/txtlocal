import { fakeFetch } from "@/test/fakeFetch";
import type { FakeFetch } from "@/test/fakeFetch";
import { EMAIL_SENDER } from "@/test/fixtures/automation";
import { OWNER_ROW } from "@/test/fixtures/identity";
import { DEDICATED_OVERVIEW } from "@/test/fixtures/senders";
import { renderWithProviders } from "@/test/render";

import { EmailSmsScreen } from "./EmailSmsScreen";

export function renderEmailSms(routes: Record<string, unknown> = {}): FakeFetch {
  const fetcher = fakeFetch({
    "GET /api/app/account/users": [OWNER_ROW],
    "GET /api/app/email-senders": [EMAIL_SENDER],
    "GET /api/app/senders": DEDICATED_OVERVIEW,
    ...routes,
  });
  renderWithProviders(<EmailSmsScreen />, { fetcher });

  return fetcher;
}
