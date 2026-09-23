import type { UserRow } from "@/api/generated/dashboard";
import { Badge } from "@/components/Badge/Badge";
import { PhoneNumber } from "@/components/PhoneNumber/PhoneNumber";
import { RowAction } from "@/components/RowAction/RowAction";
import { Table } from "@/components/Table/Table";
import type { Column, Sort } from "@/components/Table/Table";

import { sortSubaccounts } from "./rules";

import styles from "./SubaccountsTable.module.css";

const EMPTY_MSG = "No subaccounts match your search.";
const OWNER_BADGE = "Owner";
const REGENERATE_LABEL = "Regenerate";

const regenerateName = (username: string) => `Regenerate API key for ${username}`;

interface Props {
  onRegenerate: (user: UserRow) => void;
  onSort: (key: string) => void;
  rows: readonly UserRow[];
  sort: Sort;
}

export function SubaccountsTable({ onRegenerate, onSort, rows, sort }: Props) {
  return (
    <Table
      columns={columnsFor(onRegenerate)}
      emptyText={EMPTY_MSG}
      keyOf={(row) => row.userId}
      onSort={onSort}
      rows={sortSubaccounts(rows, sort)}
      sort={sort}
    />
  );
}

function columnsFor(onRegenerate: (user: UserRow) => void): readonly Column<UserRow>[] {
  return [
    {
      header: "USERNAME",
      key: "username",
      render: (row) => (
        <span className={styles.username}>
          {row.username} {row.role === "OWNER" ? <Badge tone="success">{OWNER_BADGE}</Badge> : null}
        </span>
      ),
    },
    {
      header: "API KEY",
      key: "apiKey",
      render: (row) => (
        <span className={styles.key}>
          {row.apiKeyPrefix}…
          <RowAction
            aria-label={regenerateName(row.username)}
            onClick={() => {
              onRegenerate(row);
            }}
            tone="danger"
          >
            {REGENERATE_LABEL}
          </RowAction>
        </span>
      ),
    },
    { header: "EMAIL ADDRESS", key: "email", render: (row) => row.username },
    {
      header: "PHONE NUMBER",
      key: "phone",
      render: (row) => (row.phone ? <PhoneNumber e164={row.phone} /> : ""),
    },
    { header: "NOTES", key: "notes", render: (row) => row.notes ?? "" },
  ];
}
