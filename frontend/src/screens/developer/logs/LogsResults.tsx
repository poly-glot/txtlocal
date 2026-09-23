import { Button } from "@/components/Button/Button";
import type { LogRow } from "@/api/generated/dashboard";

import { LogsTable } from "./LogsTable";

import styles from "./LogsResults.module.css";

const NEXT_LABEL = "Next";
const PREV_LABEL = "Previous";
const REFRESH_LABEL = "Refresh table";

const pageInfoText = (page: number, pageCount: number) =>
  `Page ${String(page)} of ${String(pageCount)}`;
const resultsText = (n: number) => `${String(n)} Results`;

interface Props {
  onPageChange: (page: number) => void;
  onRefresh: () => void;
  page: number;
  perPage: number;
  rows: readonly LogRow[];
  timezone: string | undefined;
}

export function LogsResults({ onPageChange, onRefresh, page, perPage, rows, timezone }: Props) {
  const pageCount = Math.max(1, Math.ceil(rows.length / perPage));
  const currentPage = Math.min(page, pageCount - 1);
  const paged = rows.slice(currentPage * perPage, currentPage * perPage + perPage);

  return (
    <div className={styles.results}>
      <LogsTable rows={paged} timezone={timezone} />
      <div className={styles.footer}>
        <p className={styles.count}>{resultsText(rows.length)}</p>
        <div className={styles.pager}>
          <Button
            disabled={currentPage === 0}
            onClick={() => {
              onPageChange(currentPage - 1);
            }}
            variant="secondary"
          >
            {PREV_LABEL}
          </Button>
          <span className={styles.pageInfo}>{pageInfoText(currentPage + 1, pageCount)}</span>
          <Button
            disabled={currentPage >= pageCount - 1}
            onClick={() => {
              onPageChange(currentPage + 1);
            }}
            variant="secondary"
          >
            {NEXT_LABEL}
          </Button>
        </div>
        <Button onClick={onRefresh} variant="secondary">
          {REFRESH_LABEL}
        </Button>
      </div>
    </div>
  );
}
