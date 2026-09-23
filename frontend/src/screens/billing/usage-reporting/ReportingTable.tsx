import type { ReportingRow } from "@/api/generated/dashboard";
import { Money } from "@/components/Money/Money";
import { PhoneNumber } from "@/components/PhoneNumber/PhoneNumber";
import { Table } from "@/components/Table/Table";
import type { Column, Sort } from "@/components/Table/Table";
import { sortRows } from "@/components/Table/sort";

import { numericSortKey, productLabel, usernameOf } from "../rules";
import { countryLabel, formatDay } from "./rules";

const EMPTY_MSG = "No results for this filter.";

type Lookup = ReadonlyMap<string, string>;
type SortValue = (row: ReportingRow, lookup: Lookup) => string;

const byDay: SortValue = (row) => row.day;

const SORT_VALUES: Readonly<Record<string, SortValue>> = {
  country: (row) => countryLabel(row.country),
  day: byDay,
  priceMicro: (row) => numericSortKey(row.priceMicro),
  product: (row) => productLabel(row.product),
  quantity: (row) => numericSortKey(row.quantity),
  senderId: (row) => row.senderId,
  totalMicro: (row) => numericSortKey(row.totalMicro),
  userId: (row, lookup) => usernameOf(lookup, row.userId),
};

interface Props {
  lookup: Lookup;
  onSort: (key: string) => void;
  rows: readonly ReportingRow[];
  sort: Sort;
}

export function ReportingTable({ lookup, onSort, rows, sort }: Props) {
  const sortValue = SORT_VALUES[sort.key] ?? byDay;

  return (
    <Table
      columns={columnsFor(lookup)}
      emptyText={EMPTY_MSG}
      keyOf={rowKey}
      onSort={onSort}
      rows={sortRows(rows, sort, (row) => sortValue(row, lookup))}
      sort={sort}
    />
  );
}

function rowKey(row: ReportingRow): string {
  return `${row.day}-${row.product}-${row.userId}-${row.senderId}-${row.country}`;
}

function columnsFor(lookup: Lookup): readonly Column<ReportingRow>[] {
  return [
    { header: "DATE", key: "day", render: (row) => formatDay(row.day) },
    { header: "PRODUCT", key: "product", render: (row) => productLabel(row.product) },
    { header: "SUBACCOUNT", key: "userId", render: (row) => usernameOf(lookup, row.userId) },
    {
      header: "SENDER ID",
      key: "senderId",
      render: (row) => <PhoneNumber e164={row.senderId} />,
    },
    { header: "COUNTRY", key: "country", render: (row) => countryLabel(row.country) },
    {
      align: "end",
      header: "PRICE",
      key: "priceMicro",
      render: (row) => <Money micro={row.priceMicro} places={4} />,
    },
    { align: "end", header: "QUANTITY", key: "quantity", render: (row) => String(row.quantity) },
    {
      align: "end",
      header: "TOTAL",
      key: "totalMicro",
      render: (row) => <Money micro={row.totalMicro} places={2} />,
    },
  ];
}
