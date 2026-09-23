import type { LedgerEntry } from "@/api/generated/dashboard";
import { Badge } from "@/components/Badge/Badge";
import { Icon } from "@/components/Icon/Icon";
import { Money } from "@/components/Money/Money";
import { Table } from "@/components/Table/Table";
import type { Column, Sort } from "@/components/Table/Table";
import { dateTimeIn } from "@/lib/format";

import styles from "./TransactionsTable.module.css";

const CREDIT_SIGN = "+";
const EMPTY_MSG = "No transactions";
const NO_VALUE = "—";
const PAID_LABEL = "Paid";

const invoiceLinkName = (invoiceNumber: string) => `Invoice ${invoiceNumber} (opens in a new tab)`;

interface Props {
  onSort: (key: string) => void;
  rows: readonly LedgerEntry[];
  sort: Sort;
  timezone: string | undefined;
}

interface InvoiceProps {
  entry: LedgerEntry;
}

export function TransactionsTable({ onSort, rows, sort, timezone }: Props) {
  return (
    <Table
      columns={columnsFor(timezone)}
      emptyText={EMPTY_MSG}
      keyOf={(row) => row.entryId}
      onSort={onSort}
      rows={rows}
      sort={sort}
    />
  );
}

function columnsFor(timezone: string | undefined): readonly Column<LedgerEntry>[] {
  return [
    {
      header: "INVOICE #",
      key: "stripeInvoiceNumber",
      render: (row) => <Invoice entry={row} />,
      sortable: false,
    },
    {
      header: "DATE",
      key: "createdAt",
      render: (row) => dateTimeIn(row.createdAt, timezone, "medium"),
    },
    {
      header: "STATUS",
      key: "status",
      render: () => <Badge tone="success">{PAID_LABEL}</Badge>,
      sortable: false,
    },
    {
      align: "end",
      header: "AMOUNT",
      key: "amountMicro",
      render: (row) => (
        <span className={styles.amount}>
          {CREDIT_SIGN}
          <Money micro={row.amountMicro} />
        </span>
      ),
      sortable: false,
    },
  ];
}

function Invoice({ entry }: InvoiceProps) {
  const { stripeInvoiceNumber: invoiceNumber, stripeInvoiceUrl: invoiceUrl } = entry;

  if (typeof invoiceNumber !== "string" || typeof invoiceUrl !== "string") {
    return invoiceNumber ?? NO_VALUE;
  }

  return (
    <a
      aria-label={invoiceLinkName(invoiceNumber)}
      className={styles.invoice}
      href={invoiceUrl}
      rel="noreferrer"
      target="_blank"
    >
      {invoiceNumber}
      <Icon name="external" size={14} />
    </a>
  );
}
