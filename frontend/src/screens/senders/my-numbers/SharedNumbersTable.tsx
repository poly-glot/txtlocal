import type { SenderView } from "@/api/generated/dashboard";
import { Badge } from "@/components/Badge/Badge";
import { Table } from "@/components/Table/Table";
import type { Column } from "@/components/Table/Table";

import { GLOBE } from "./rules";

const EMPTY_MSG = "No shared numbers are enabled for this account.";
const SHARED_NAME = "Shared number";

const COLUMNS: readonly Column<SenderView>[] = [
  { header: "Country", key: "country", render: () => GLOBE },
  { header: "Name", key: "name", render: () => SHARED_NAME },
  { header: "Use for", key: "useFor", render: (row) => row.capabilities.join(", ") },
  {
    header: "Status",
    key: "status",
    render: (row) => <Badge tone="success">{row.statusLabel}</Badge>,
  },
];

interface Props {
  rows: readonly SenderView[];
}

export function SharedNumbersTable({ rows }: Props) {
  return (
    <Table columns={COLUMNS} emptyText={EMPTY_MSG} keyOf={(row) => row.senderId} rows={rows} />
  );
}
