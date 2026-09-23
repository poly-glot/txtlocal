import type { EmailSender, SendersView } from "@/api/generated/dashboard";
import { RowAction } from "@/components/RowAction/RowAction";
import { Table } from "@/components/Table/Table";
import type { Column } from "@/components/Table/Table";

import type { SubaccountOption } from "./rules";
import { senderDisplay, subaccountLabel } from "./rules";

import styles from "./AllowedAddressesTable.module.css";

const EMPTY_MSG = "No allowed addresses yet.";
const REMOVE_LABEL = "Remove";

const removeName = (email: string) => `${REMOVE_LABEL} ${email}`;

interface Props {
  onRemove: (row: EmailSender) => void;
  rows: readonly EmailSender[];
  senders: SendersView;
  subaccounts: readonly SubaccountOption[];
}

export function AllowedAddressesTable({ onRemove, rows, senders, subaccounts }: Props) {
  return (
    <Table
      columns={columnsFor(onRemove, senders, subaccounts)}
      emptyText={EMPTY_MSG}
      keyOf={(row) => row.email}
      rows={rows}
    />
  );
}

function columnsFor(
  onRemove: (row: EmailSender) => void,
  senders: SendersView,
  subaccounts: readonly SubaccountOption[],
): readonly Column<EmailSender>[] {
  return [
    {
      header: "SUBACCOUNT NAME",
      key: "userId",
      render: (row) => subaccountLabel(subaccounts, row.userId),
    },
    { header: "EMAIL ADDRESS", key: "email", render: (row) => row.email },
    {
      header: "SENDER NUMBER",
      key: "senderId",
      render: (row) => (
        <span className={styles.cell}>
          {senderDisplay(senders, row.senderId ?? null)}
          <RowAction
            aria-label={removeName(row.email)}
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
