import { keepPreviousData } from "@tanstack/react-query";
import { useState } from "react";

import type { ReportingPage } from "@/api/generated/dashboard";
import { useApiQuery } from "@/api/queries";
import { Panel } from "@/components/Panel/Panel";
import { StatusPanel } from "@/components/StatusPanel/StatusPanel";
import type { Sort } from "@/components/Table/Table";
import { toggleSort } from "@/components/Table/sort";
import { Toast } from "@/components/Toast/Toast";
import { dataOf } from "@/lib/format";
import { undismissedRefusalNotice } from "@/lib/notice";

import { usernameLookup } from "../rules";
import { ReportingExport } from "./ReportingExport";
import { ReportingFilters } from "./ReportingFilters";
import { ReportingPager } from "./ReportingPager";
import { ReportingTable } from "./ReportingTable";
import { DEFAULT_PAGE_SIZE, useReportingControls } from "./useReportingControls";

import styles from "./UsageReportingScreen.module.css";

const EMPTY_PAGE: ReportingPage = {
  page: 1,
  pageSize: DEFAULT_PAGE_SIZE,
  rows: [],
  totalResults: 0,
};
const NOTE = "Today's usage appears tomorrow.";
const TITLE = "Usage Reporting";

interface Props {
  now?: Date;
}

export function UsageReportingScreen({ now = new Date() }: Props) {
  const controls = useReportingControls(now);
  const [sort, setSort] = useState<Sort>({ direction: "desc", key: "day" });
  const [dismissedAt, setDismissedAt] = useState(0);
  const reporting = useApiQuery(
    "get",
    "/api/app/analytics/reporting",
    { params: { query: controls.query } },
    { placeholderData: keepPreviousData },
  );
  const users = useApiQuery(
    "get",
    "/api/app/account/users",
    { params: { query: { q: "" } } },
    { placeholderData: keepPreviousData },
  );

  if (reporting.data === undefined) {
    return <StatusPanel title={TITLE} />;
  }

  const accountUsers = users.data?.status === "OK" ? users.data.data : [];
  const lookup = usernameLookup(accountUsers);
  const { rows, totalResults } = dataOf(reporting.data, EMPTY_PAGE);
  const notice = undismissedRefusalNotice(reporting.data, dismissedAt, reporting.dataUpdatedAt);

  return (
    <Panel actions={<ReportingExport filters={controls.filters} />} title={TITLE}>
      <Toast
        notice={notice}
        onDismiss={() => {
          setDismissedAt(reporting.dataUpdatedAt);
        }}
      />
      <ReportingFilters
        filters={controls.filters}
        onChange={controls.changeFilters}
        users={accountUsers}
      />
      <div className={styles.results}>
        <ReportingTable
          lookup={lookup}
          onSort={(key) => {
            setSort(toggleSort(sort, key));
          }}
          rows={rows}
          sort={sort}
        />
        <ReportingPager
          onPageChange={controls.setPage}
          onPageSizeChange={controls.changePageSize}
          page={controls.page}
          pageSize={controls.pageSize}
          totalResults={totalResults}
        />
        <p className={styles.note}>{NOTE}</p>
      </div>
    </Panel>
  );
}
