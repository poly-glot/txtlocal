import { useState } from "react";
import { Link } from "react-router";

import type { LogsPage } from "@/api/generated/dashboard";
import { Panel } from "@/components/Panel/Panel";
import { StatusPanel } from "@/components/StatusPanel/StatusPanel";
import { Toast } from "@/components/Toast/Toast";
import { dataOf } from "@/lib/format";
import { undismissedRefusalNotice } from "@/lib/notice";
import { API_DOCS_PATH } from "@/lib/paths";
import { useAccountTimezone } from "@/lib/useAccountTimezone";

import { LogsFilters } from "./LogsFilters";
import { LogsResults } from "./LogsResults";
import { LogsTiles } from "./LogsTiles";
import { INITIAL_LOGS_FILTERS } from "./rules";
import { useLogs } from "./useLogs";

import styles from "./ApiLogsScreen.module.css";

const DOCS_LABEL = "API Documentation";
const EMPTY_LEAD = "Kick things off — send";
const EMPTY_LINK_TEXT = "your first message";
const EMPTY_TITLE = "No SMS activity yet.";
const GUIDE_LABEL = "Guide to API Logs";
const QUICK_SMS_PATH = "/sms/quick";
const RETENTION_NOTE = "Logs are retained for 7 days.";
const SECTION_TITLE = "Your recent activity";
const TITLE = "Developer Tools";
const ZERO_LOGS_PAGE: LogsPage = {
  resultsPerPage: 20,
  rows: [],
  tiles: { failed: 0, successful: 0, total: 0 },
};

const LINKS = (
  <div className={styles.links}>
    <Link to={API_DOCS_PATH}>{DOCS_LABEL}</Link>
    <span aria-disabled="true" className={styles.inertLink}>
      {GUIDE_LABEL}
    </span>
  </div>
);

export function ApiLogsScreen() {
  const [filters, setFilters] = useState(INITIAL_LOGS_FILTERS);
  const [page, setPage] = useState(0);
  const [dismissedAt, setDismissedAt] = useState(0);
  const logs = useLogs(filters);
  const timezone = useAccountTimezone();

  if (logs.data === undefined) {
    return <StatusPanel title={TITLE} />;
  }

  const { resultsPerPage, rows, tiles } = dataOf(logs.data, ZERO_LOGS_PAGE);
  const notice = logs.isPlaceholderData
    ? undefined
    : undismissedRefusalNotice(logs.data, dismissedAt, logs.dataUpdatedAt);

  return (
    <Panel actions={LINKS} title={TITLE}>
      <section className={styles.activity}>
        <div className={styles.intro}>
          <h3 className={styles.sectionTitle}>{SECTION_TITLE}</h3>
          <p className={styles.note}>{RETENTION_NOTE}</p>
        </div>
        <LogsTiles tiles={tiles} />
      </section>
      <LogsFilters
        filters={filters}
        onChange={(next) => {
          setFilters(next);
          setPage(0);
        }}
      />
      {rows.length === 0 ? (
        <p className={styles.empty}>
          {EMPTY_TITLE} {EMPTY_LEAD} <Link to={QUICK_SMS_PATH}>{EMPTY_LINK_TEXT}</Link>.
        </p>
      ) : (
        <LogsResults
          onPageChange={setPage}
          onRefresh={() => {
            void logs.refetch();
          }}
          page={page}
          perPage={resultsPerPage}
          rows={rows}
          timezone={timezone}
        />
      )}
      <Toast
        notice={notice}
        onDismiss={() => {
          setDismissedAt(logs.dataUpdatedAt);
        }}
      />
    </Panel>
  );
}
