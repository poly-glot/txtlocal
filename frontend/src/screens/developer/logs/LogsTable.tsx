import type { LogRow } from "@/api/generated/dashboard";
import { Badge } from "@/components/Badge/Badge";
import { Table } from "@/components/Table/Table";
import type { Column } from "@/components/Table/Table";
import { dateTimeIn } from "@/lib/format";

import { outcomeTone } from "./rules";

const EMPTY_MSG = "No results";

interface Props {
  rows: readonly LogRow[];
  timezone: string | undefined;
}

export function LogsTable({ rows, timezone }: Props) {
  return (
    <Table
      columns={columnsFor(timezone)}
      emptyText={EMPTY_MSG}
      keyOf={(row) => row.requestId}
      rows={rows}
    />
  );
}

function columnsFor(timezone: string | undefined): readonly Column<LogRow>[] {
  return [
    { header: "DATE", key: "date", render: (row) => dateTimeIn(row.timestamp, timezone, "short") },
    { header: "SUBACCOUNT", key: "subaccount", render: (row) => row.userId },
    { header: "METHOD", key: "method", render: (row) => row.method },
    { header: "ENDPOINT", key: "endpoint", render: (row) => row.route },
    {
      header: "STATUS",
      key: "status",
      render: (row) => <Badge tone={outcomeTone(row.outcome)}>{row.status}</Badge>,
    },
    {
      align: "end",
      header: "DURATION",
      key: "duration",
      render: (row) => `${String(row.latencyMs)} ms`,
    },
    { header: "REQUEST ID", key: "requestId", render: (row) => row.requestId },
  ];
}
