import { useId, useState } from "react";
import type { ReactNode } from "react";

import { CursorPager } from "@/components/CursorPager/CursorPager";
import { EntriesSelect } from "@/components/EntriesSelect/EntriesSelect";
import { ENTRY_SIZES } from "@/components/EntriesSelect/entrySizes";
import { useCursorTrail } from "@/lib/useCursorTrail";

import { pageOf } from "./pageOf";

import styles from "./PagedRows.module.css";

interface Props<Row> {
  children: (rows: readonly Row[]) => ReactNode;
  rows: readonly Row[];
}

export function PagedRows<Row>({ children, rows }: Props<Row>) {
  const entriesId = useId();
  const [limit, setLimit] = useState<number>(ENTRY_SIZES[0]);
  const trail = useCursorTrail(`${String(limit)}|${String(rows.length)}`);
  const page = pageOf(rows, trail.cursor, limit);

  return (
    <>
      {children(page.rows)}
      <div className={styles.footer}>
        <EntriesSelect id={entriesId} onChange={setLimit} value={limit} />
        <CursorPager nextCursor={page.nextCursor} trail={trail} />
      </div>
    </>
  );
}
