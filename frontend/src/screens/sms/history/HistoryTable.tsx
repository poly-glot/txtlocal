import type { MessageRow } from "@/api/generated/dashboard";
import { Badge } from "@/components/Badge/Badge";
import { PhoneNumber } from "@/components/PhoneNumber/PhoneNumber";
import { Table } from "@/components/Table/Table";
import type { Column, Sort } from "@/components/Table/Table";
import { sortRows } from "@/components/Table/sort";
import { dateTimeIn } from "@/lib/format";

import { STATUS_DISPLAY } from "./rules";

import styles from "./HistoryTable.module.css";

const EMPTY_MSG = "No results";

const openLabel = (to: string) => `Open message to ${to}`;

interface Props {
  onSelect: (messageId: string) => void;
  onSort: (key: string) => void;
  rows: readonly MessageRow[];
  sort: Sort;
  timezone: string | undefined;
}

export function HistoryTable({ onSelect, onSort, rows, sort, timezone }: Props) {
  return (
    <Table
      columns={columnsFor(onSelect, timezone)}
      emptyText={EMPTY_MSG}
      keyOf={(row) => row.messageId}
      onSort={onSort}
      rows={sortRows(rows, sort, valueOf)}
      sort={sort}
    />
  );
}

function columnsFor(
  onSelect: (messageId: string) => void,
  timezone: string | undefined,
): readonly Column<MessageRow>[] {
  return [
    { header: "USERNAME", key: "username", render: (row) => row.username },
    { header: "DATE", key: "date", render: (row) => dateTimeIn(row.queuedAt, timezone, "short") },
    { header: "FROM", key: "from", render: (row) => <PhoneNumber e164={row.from} /> },
    { header: "TO", key: "to", render: (row) => <PhoneNumber e164={row.to} /> },
    {
      header: "STATUS",
      key: "status",
      render: (row) => (
        <Badge tone={STATUS_DISPLAY[row.status].tone}>{STATUS_DISPLAY[row.status].label}</Badge>
      ),
    },
    {
      header: "BODY",
      key: "body",
      render: (row) => (
        <button
          aria-label={openLabel(row.to)}
          className={styles.open}
          onClick={() => {
            onSelect(row.messageId);
          }}
          type="button"
        >
          {row.body}
        </button>
      ),
    },
  ];
}

function valueOf(row: MessageRow, key: string): string {
  switch (key) {
    case "body":
      return row.body;
    case "date":
      return row.queuedAt;
    case "from":
      return row.from;
    case "status":
      return row.status;
    case "to":
      return row.to;
    default:
      return row.username;
  }
}
