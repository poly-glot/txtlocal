import type { UpcomingCharge } from "@/api/generated/dashboard";
import { useApiQuery } from "@/api/queries";
import { Money } from "@/components/Money/Money";
import { Panel } from "@/components/Panel/Panel";
import { PhoneNumber } from "@/components/PhoneNumber/PhoneNumber";
import { StatusPanel } from "@/components/StatusPanel/StatusPanel";
import { Table } from "@/components/Table/Table";
import type { Column } from "@/components/Table/Table";
import { dateTimeIn } from "@/lib/format";
import { useAccountTimezone } from "@/lib/useAccountTimezone";

const EMPTY_MSG = "There's nothing here right now";
const TITLE = "Upcoming Charges";

export function UpcomingChargesScreen() {
  const timezone = useAccountTimezone();
  const charges = useApiQuery("get", "/api/app/billing/upcoming-charges");

  if (charges.data === undefined) {
    return <StatusPanel title={TITLE} />;
  }
  if (charges.data.status === "ERROR") {
    return <StatusPanel error={charges.data.message} title={TITLE} />;
  }

  return (
    <Panel title={TITLE}>
      <Table
        columns={columnsFor(timezone)}
        emptyText={EMPTY_MSG}
        keyOf={(row) => row.value}
        rows={charges.data.data}
      />
    </Panel>
  );
}

function columnsFor(timezone: string | undefined): readonly Column<UpcomingCharge>[] {
  return [
    { header: "NUMBER", key: "value", render: (row) => <PhoneNumber e164={row.value} /> },
    {
      header: "NEXT CHARGE",
      key: "renewsAt",
      render: (row) => dateTimeIn(row.renewsAt, timezone, "medium"),
    },
    {
      align: "end",
      header: "AMOUNT",
      key: "monthlyPriceMicro",
      render: (row) => <Money micro={row.monthlyPriceMicro} />,
    },
  ];
}
