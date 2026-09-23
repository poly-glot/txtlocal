import type { UsageTabRow } from "@/api/generated/dashboard";
import { Money } from "@/components/Money/Money";
import { Table } from "@/components/Table/Table";
import type { Column, Sort } from "@/components/Table/Table";
import { sortRows } from "@/components/Table/sort";

import { numericSortKey, productLabel, usernameOf } from "../rules";
import { formatMonthColumn } from "./rules";

const EMPTY_MSG = "No usage for this month.";

type Lookup = ReadonlyMap<string, string>;
type SortValue = (row: UsageTabRow, lookup: Lookup) => string;

const byMonth: SortValue = (row) => row.month;

const SORT_VALUES: Readonly<Record<string, SortValue>> = {
  costMicro: (row) => numericSortKey(row.costMicro),
  month: byMonth,
  product: (row) => productLabel(row.product),
  quantity: (row) => numericSortKey(row.quantity),
  username: (row, lookup) => usernameOf(lookup, row.userId),
};

interface Props {
  lookup: Lookup;
  onSort: (key: string) => void;
  rows: readonly UsageTabRow[];
  sort: Sort;
}

export function UsageTable({ lookup, onSort, rows, sort }: Props) {
  const sortValue = SORT_VALUES[sort.key] ?? byMonth;

  return (
    <Table
      columns={columnsFor(lookup)}
      emptyText={EMPTY_MSG}
      keyOf={(row) => `${row.product}-${row.userId}`}
      onSort={onSort}
      rows={sortRows(rows, sort, (row) => sortValue(row, lookup))}
      sort={sort}
    />
  );
}

function columnsFor(lookup: Lookup): readonly Column<UsageTabRow>[] {
  return [
    { header: "DATE", key: "month", render: (row) => formatMonthColumn(row.month) },
    { header: "PRODUCT", key: "product", render: (row) => productLabel(row.product) },
    { header: "USERNAME", key: "username", render: (row) => usernameOf(lookup, row.userId) },
    { align: "end", header: "QUANTITY", key: "quantity", render: (row) => String(row.quantity) },
    {
      align: "end",
      header: "COST",
      key: "costMicro",
      render: (row) => <Money micro={row.costMicro} places={4} />,
    },
  ];
}
