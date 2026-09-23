import type { CatalogueNumber } from "@/api/generated/dashboard";
import { Button } from "@/components/Button/Button";
import { Money } from "@/components/Money/Money";
import { PhoneNumber } from "@/components/PhoneNumber/PhoneNumber";
import { Table } from "@/components/Table/Table";
import type { Column } from "@/components/Table/Table";

import { countryLabel } from "../rules";
import { NumberPager } from "./NumberPager";

import styles from "./NumberCatalogueTable.module.css";

const BUY_LABEL = "Buy";
const EMPTY_MSG = "No numbers match your filters.";
const PRICE_SUFFIX = "/ Month";

const buyName = (number: string) => `Buy ${number}`;

type Buy = (number: CatalogueNumber) => void;

interface Props {
  onBuy: Buy;
  onPage: (page: number) => void;
  page: number;
  rows: readonly CatalogueNumber[];
  totalPages: number;
}

export function NumberCatalogueTable({ onBuy, onPage, page, rows, totalPages }: Props) {
  return (
    <div className={styles.wrapper}>
      <Table
        columns={columnsFor(onBuy)}
        emptyText={EMPTY_MSG}
        keyOf={(row) => row.value}
        rows={rows}
      />
      <NumberPager onPage={onPage} page={page} totalPages={totalPages} />
    </div>
  );
}

function columnsFor(onBuy: Buy): readonly Column<CatalogueNumber>[] {
  return [
    { header: "Number", key: "number", render: (row) => <PhoneNumber e164={row.value} /> },
    { header: "Country", key: "country", render: (row) => countryLabel(row.country) },
    { header: "Use for", key: "useFor", render: (row) => row.capabilities.join(", ") },
    {
      align: "end",
      header: "Price",
      key: "price",
      render: (row) => (
        <>
          <Money micro={row.monthlyPriceMicro} /> {PRICE_SUFFIX}
        </>
      ),
    },
    {
      align: "end",
      header: BUY_LABEL,
      key: "buy",
      render: (row) => (
        <Button
          aria-label={buyName(row.value)}
          onClick={() => {
            onBuy(row);
          }}
          variant="tonal"
        >
          {BUY_LABEL}
        </Button>
      ),
    },
  ];
}
