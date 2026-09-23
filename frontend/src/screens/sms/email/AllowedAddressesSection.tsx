import { keepPreviousData } from "@tanstack/react-query";

import { useApiQuery } from "@/api/queries";
import { StatusPanel } from "@/components/StatusPanel/StatusPanel";
import { dataOf } from "@/lib/format";
import { EMPTY_SENDERS_VIEW } from "@/rules/senders";

import { AllowedAddressesPanel } from "./AllowedAddressesPanel";

const HEADING = "Allowed Addresses";

export function AllowedAddressesSection() {
  const emailSenders = useApiQuery("get", "/api/app/email-senders");
  const senders = useApiQuery("get", "/api/app/senders");
  const subaccounts = useApiQuery(
    "get",
    "/api/app/account/users",
    { params: { query: { q: "" } } },
    { placeholderData: keepPreviousData },
  );

  if (emailSenders.data === undefined) {
    return <StatusPanel title={HEADING} />;
  }
  if (emailSenders.data.status === "ERROR") {
    return <StatusPanel error={emailSenders.data.message} title={HEADING} />;
  }

  return (
    <AllowedAddressesPanel
      rows={emailSenders.data.data}
      senders={dataOf(senders.data, EMPTY_SENDERS_VIEW)}
      subaccounts={dataOf(subaccounts.data, [])}
      title={HEADING}
    />
  );
}
