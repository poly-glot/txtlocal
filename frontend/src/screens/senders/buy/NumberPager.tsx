import { Button } from "@/components/Button/Button";

import { pageNumbers } from "./rules";

import styles from "./NumberPager.module.css";

const NEXT_LABEL = "Next page";
const PREVIOUS_LABEL = "Previous page";

const pageText = (page: number, totalPages: number) =>
  `Page ${String(page)} of ${String(totalPages)}`;

interface Props {
  onPage: (page: number) => void;
  page: number;
  totalPages: number;
}

export function NumberPager({ onPage, page, totalPages }: Props) {
  return (
    <nav aria-label="Pagination" className={styles.footer}>
      <span className={styles.note}>{pageText(page, totalPages)}</span>
      <div className={styles.pager}>
        <Button
          aria-label={PREVIOUS_LABEL}
          disabled={page <= 1}
          onClick={() => {
            onPage(page - 1);
          }}
          variant="secondary"
        >
          {"<"}
        </Button>
        {pageNumbers(totalPages).map((number) => (
          <Button
            aria-current={number === page ? "page" : undefined}
            key={number}
            onClick={() => {
              onPage(number);
            }}
            variant={number === page ? "primary" : "secondary"}
          >
            {number}
          </Button>
        ))}
        <Button
          aria-label={NEXT_LABEL}
          disabled={page >= totalPages}
          onClick={() => {
            onPage(page + 1);
          }}
          variant="secondary"
        >
          {">"}
        </Button>
      </div>
    </nav>
  );
}
