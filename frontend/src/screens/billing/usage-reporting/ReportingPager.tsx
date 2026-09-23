import { Button } from "@/components/Button/Button";
import { Select } from "@/components/Select/Select";

import styles from "./ReportingPager.module.css";

const FIRST_LABEL = "First";
const LAST_LABEL = "Last";
const NEXT_LABEL = "Next";
const PAGE_SIZE_LABEL = "Per page";
const PAGE_SIZE_OPTIONS = [
  { label: "10 per page", value: "10" },
  { label: "25 per page", value: "25" },
  { label: "50 per page", value: "50" },
];
const PREV_LABEL = "Previous";

const pageInfoText = (page: number, pageCount: number) =>
  `Page ${String(page)} of ${String(pageCount)}`;
const resultsText = (n: number) => `${String(n)} results`;

interface Props {
  onPageChange: (page: number) => void;
  onPageSizeChange: (pageSize: number) => void;
  page: number;
  pageSize: number;
  totalResults: number;
}

export function ReportingPager({
  onPageChange,
  onPageSizeChange,
  page,
  pageSize,
  totalResults,
}: Props) {
  const pageCount = Math.max(1, Math.ceil(totalResults / pageSize));

  return (
    <div className={styles.footer}>
      <div className={styles.range}>
        <p className={styles.count}>{resultsText(totalResults)}</p>
        <Select
          id="reporting-page-size"
          label={PAGE_SIZE_LABEL}
          labelHidden
          onChange={(event) => {
            onPageSizeChange(Number(event.target.value));
          }}
          options={PAGE_SIZE_OPTIONS}
          value={String(pageSize)}
        />
      </div>
      <div className={styles.pager}>
        <Button
          disabled={page === 1}
          onClick={() => {
            onPageChange(1);
          }}
          variant="secondary"
        >
          {FIRST_LABEL}
        </Button>
        <Button
          disabled={page === 1}
          onClick={() => {
            onPageChange(page - 1);
          }}
          variant="secondary"
        >
          {PREV_LABEL}
        </Button>
        <span className={styles.pageInfo}>{pageInfoText(page, pageCount)}</span>
        <Button
          disabled={page >= pageCount}
          onClick={() => {
            onPageChange(page + 1);
          }}
          variant="secondary"
        >
          {NEXT_LABEL}
        </Button>
        <Button
          disabled={page >= pageCount}
          onClick={() => {
            onPageChange(pageCount);
          }}
          variant="secondary"
        >
          {LAST_LABEL}
        </Button>
      </div>
    </div>
  );
}
