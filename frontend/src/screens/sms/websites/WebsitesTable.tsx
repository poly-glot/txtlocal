import type { Website } from "@/api/generated/dashboard";
import { Badge } from "@/components/Badge/Badge";
import { Table } from "@/components/Table/Table";
import type { Column } from "@/components/Table/Table";

import { WEBSITE_STATUS_DISPLAY, registeredDateDisplay } from "./rules";

import styles from "./WebsitesTable.module.css";

const EMPTY_MSG = "No websites registered yet.";

function statusCell(row: Website) {
  const status = WEBSITE_STATUS_DISPLAY[row.status];

  return (
    <>
      <Badge tone={status.tone}>{status.label}</Badge>
      {row.rejectedReason ? <p className={styles.reason}>{row.rejectedReason}</p> : null}
    </>
  );
}

const COLUMNS: readonly Column<Website>[] = [
  { header: "WEBSITE", key: "domain", render: (row) => row.domain },
  {
    header: "DATE REGISTERED",
    key: "registeredAt",
    render: (row) => registeredDateDisplay(row.registeredAt),
  },
  { header: "STATUS", key: "status", render: statusCell },
];

interface Props {
  rows: readonly Website[];
}

export function WebsitesTable({ rows }: Props) {
  return <Table columns={COLUMNS} emptyText={EMPTY_MSG} keyOf={(row) => row.domain} rows={rows} />;
}
