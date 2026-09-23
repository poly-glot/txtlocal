import { useState } from "react";

import { Button } from "@/components/Button/Button";
import { Panel } from "@/components/Panel/Panel";
import { StatusPanel } from "@/components/StatusPanel/StatusPanel";
import type { Sort } from "@/components/Table/Table";
import { toggleSort } from "@/components/Table/sort";
import { useAccountTimezone } from "@/lib/useAccountTimezone";

import { TransactionsTable } from "./TransactionsTable";
import { useTransactions } from "./useTransactions";

import styles from "./TransactionsScreen.module.css";

const LOAD_MORE_LABEL = "Load more";
const TITLE = "Transactions";

export function TransactionsScreen() {
  const [sort, setSort] = useState<Sort>({ direction: "desc", key: "createdAt" });
  const timezone = useAccountTimezone();
  const transactions = useTransactions(sort.direction);
  const pages = transactions.data?.pages ?? [];
  const firstPage = pages[0];

  if (firstPage === undefined) {
    return <StatusPanel title={TITLE} />;
  }
  if (firstPage.status === "ERROR") {
    return <StatusPanel error={firstPage.message} title={TITLE} />;
  }

  const rows = pages.flatMap((page) => (page.status === "OK" ? page.data.items : []));

  return (
    <Panel title={TITLE}>
      <TransactionsTable
        onSort={(key) => {
          setSort(toggleSort(sort, key));
        }}
        rows={rows}
        sort={sort}
        timezone={timezone}
      />
      {transactions.hasNextPage ? (
        <div className={styles.more}>
          <Button
            disabled={transactions.isFetchingNextPage}
            onClick={() => {
              void transactions.fetchNextPage();
            }}
            variant="secondary"
          >
            {LOAD_MORE_LABEL}
          </Button>
        </div>
      ) : null}
    </Panel>
  );
}
