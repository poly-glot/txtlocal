import { keepPreviousData } from "@tanstack/react-query";
import { useState } from "react";

import { useApiQuery } from "@/api/queries";
import { Panel } from "@/components/Panel/Panel";
import { StatusPanel } from "@/components/StatusPanel/StatusPanel";
import type { Sort } from "@/components/Table/Table";
import { toggleSort } from "@/components/Table/sort";

import { usernameLookup } from "../rules";
import { UsageExport } from "./UsageExport";
import { UsageFilters } from "./UsageFilters";
import { UsageTable } from "./UsageTable";
import type { UsageFilterState } from "./rules";
import { currentMonthValue, filteredUsageRows } from "./rules";

import styles from "./UsageScreen.module.css";

const INITIAL_FILTERS: UsageFilterState = { product: "", userId: "" };
const NOTE = "Usage is updated nightly.";
const TITLE = "Usage";

interface Props {
  now?: Date;
}

export function UsageScreen({ now = new Date() }: Props) {
  const [month, setMonth] = useState(() => currentMonthValue(now));
  const [filters, setFilters] = useState<UsageFilterState>(INITIAL_FILTERS);
  const [sort, setSort] = useState<Sort>({ direction: "asc", key: "product" });
  const usage = useApiQuery("get", "/api/app/analytics/usage", { params: { query: { month } } });
  const users = useApiQuery(
    "get",
    "/api/app/account/users",
    { params: { query: { q: "" } } },
    { placeholderData: keepPreviousData },
  );

  if (usage.data === undefined) {
    return <StatusPanel title={TITLE} />;
  }
  if (usage.data.status === "ERROR") {
    return <StatusPanel error={usage.data.message} title={TITLE} />;
  }

  const accountUsers = users.data?.status === "OK" ? users.data.data : [];
  const lookup = usernameLookup(accountUsers);
  const rows = filteredUsageRows(usage.data.data.rows, filters);

  return (
    <Panel actions={<UsageExport lookup={lookup} rows={rows} />} title={TITLE}>
      <UsageFilters
        filters={filters}
        month={month}
        onFiltersChange={setFilters}
        onMonthChange={setMonth}
        users={accountUsers}
      />
      <div className={styles.results}>
        <UsageTable
          lookup={lookup}
          onSort={(key) => {
            setSort(toggleSort(sort, key));
          }}
          rows={rows}
          sort={sort}
        />
        <p className={styles.note}>{NOTE}</p>
      </div>
    </Panel>
  );
}
