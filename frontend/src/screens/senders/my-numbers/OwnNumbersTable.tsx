import type { SenderView } from "@/api/generated/dashboard";
import { Badge } from "@/components/Badge/Badge";
import { PhoneNumber } from "@/components/PhoneNumber/PhoneNumber";
import { RowAction } from "@/components/RowAction/RowAction";
import { Table } from "@/components/Table/Table";
import type { Column } from "@/components/Table/Table";

import { countryLabel } from "../rules";
import { isAwaitingVerification, lastVerifiedText } from "./rules";

import styles from "./OwnNumbersTable.module.css";

const EMPTY_MSG = "You have not added any of your own numbers yet.";
const REMOVE_LABEL = "Remove";
const REVERIFY_LABEL = "Re-verify";

const removeName = (number: string) => `Remove ${number}`;
const reverifyName = (number: string) => `Re-verify ${number}`;

type Act = (sender: SenderView) => void;

interface Props {
  onRemove: Act;
  onReverify: Act;
  rows: readonly SenderView[];
}

export function OwnNumbersTable({ onRemove, onReverify, rows }: Props) {
  return (
    <Table
      columns={columnsFor(onRemove, onReverify)}
      emptyText={EMPTY_MSG}
      keyOf={(row) => row.senderId}
      rows={rows}
    />
  );
}

function columnsFor(onRemove: Act, onReverify: Act): readonly Column<SenderView>[] {
  return [
    { header: "Country", key: "country", render: (row) => countryLabel(row.country) },
    { header: "Name", key: "name", render: (row) => row.nickname ?? "" },
    { header: "Number", key: "number", render: (row) => <PhoneNumber e164={row.value} /> },
    { header: "Last verified", key: "verified", render: (row) => lastVerifiedText(row.verifiedAt) },
    {
      header: "Status",
      key: "status",
      render: (row) => (
        <Badge tone={row.status === "READY" ? "success" : "warning"}>{row.statusLabel}</Badge>
      ),
    },
    {
      align: "end",
      header: "",
      key: "actions",
      render: (row) => (
        <span className={styles.actions}>
          {isAwaitingVerification(row) ? (
            <RowAction
              aria-label={reverifyName(row.value)}
              onClick={() => {
                onReverify(row);
              }}
            >
              {REVERIFY_LABEL}
            </RowAction>
          ) : null}
          <RowAction
            aria-label={removeName(row.value)}
            onClick={() => {
              onRemove(row);
            }}
            tone="danger"
          >
            {REMOVE_LABEL}
          </RowAction>
        </span>
      ),
    },
  ];
}
