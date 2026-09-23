import type { SenderView } from "@/api/generated/dashboard";
import { Badge } from "@/components/Badge/Badge";
import { PhoneNumber } from "@/components/PhoneNumber/PhoneNumber";
import { RowAction } from "@/components/RowAction/RowAction";
import { Table } from "@/components/Table/Table";
import type { Column } from "@/components/Table/Table";

import { countryLabel } from "../rules";
import { dedicatedBadgeTone, isCancellableDedicated, lastVerifiedText } from "./rules";

const CANCEL_LABEL = "Cancel number";
const EMPTY_MSG = "You have not purchased any dedicated numbers yet.";

const cancelName = (number: string) => `Cancel ${number}`;

type Act = (sender: SenderView) => void;

interface Props {
  onCancel: Act;
  rows: readonly SenderView[];
}

export function DedicatedNumbersTable({ onCancel, rows }: Props) {
  return (
    <Table
      columns={columnsFor(onCancel)}
      emptyText={EMPTY_MSG}
      keyOf={(row) => row.senderId}
      rows={rows}
    />
  );
}

function columnsFor(onCancel: Act): readonly Column<SenderView>[] {
  return [
    { header: "Country", key: "country", render: (row) => countryLabel(row.country) },
    { header: "Number", key: "number", render: (row) => <PhoneNumber e164={row.value} /> },
    { header: "Use for", key: "useFor", render: (row) => row.capabilities.join(", ") },
    { header: "Renews", key: "renews", render: (row) => lastVerifiedText(row.renewsAt) },
    {
      header: "Status",
      key: "status",
      render: (row) => <Badge tone={dedicatedBadgeTone(row.status)}>{row.statusLabel}</Badge>,
    },
    {
      align: "end",
      header: "",
      key: "actions",
      render: (row) =>
        isCancellableDedicated(row) ? (
          <RowAction
            aria-label={cancelName(row.value)}
            onClick={() => {
              onCancel(row);
            }}
            tone="danger"
          >
            {CANCEL_LABEL}
          </RowAction>
        ) : null,
    },
  ];
}
