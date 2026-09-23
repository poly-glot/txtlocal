import { keepPreviousData } from "@tanstack/react-query";
import { useState } from "react";

import { useApiQuery } from "@/api/queries";
import { CursorPager } from "@/components/CursorPager/CursorPager";
import { Panel } from "@/components/Panel/Panel";
import { StatusPanel } from "@/components/StatusPanel/StatusPanel";
import type { Sort } from "@/components/Table/Table";
import { toggleSort } from "@/components/Table/sort";
import { useAccountTimezone } from "@/lib/useAccountTimezone";
import { useCursorTrail } from "@/lib/useCursorTrail";

import type { ScreenProduct } from "../rules";
import { HistoryExport } from "./HistoryExport";
import { HistoryFilters } from "./HistoryFilters";
import { HistoryTable } from "./HistoryTable";
import { MessageDrawer } from "./MessageDrawer";
import { historyTitle, initialHistoryFilters } from "./rules";

import styles from "./HistoryScreen.module.css";

const ENTRIES_NOTE = "Show 20 Entries";
const RETENTION_NOTE = "Historical data is retained for 4 months.";

interface Props {
  product?: ScreenProduct;
}

export function HistoryScreen({ product = "SMS" }: Props) {
  const [filters, setFilters] = useState(() => initialHistoryFilters(product));
  const [selected, setSelected] = useState<string>();
  const [sort, setSort] = useState<Sort>({ direction: "desc", key: "date" });
  const trail = useCursorTrail(JSON.stringify(filters));
  const history = useApiQuery(
    "get",
    "/api/app/messages",
    {
      params: {
        query: trail.cursor === undefined ? filters : { ...filters, cursor: trail.cursor },
      },
    },
    { placeholderData: keepPreviousData },
  );
  const timezone = useAccountTimezone();
  const title = historyTitle(product);

  if (history.data === undefined) {
    return <StatusPanel title={title} />;
  }
  if (history.data.status === "ERROR") {
    return <StatusPanel error={history.data.message} title={title} />;
  }

  return (
    <Panel actions={<HistoryExport filters={filters} />} title={title}>
      <HistoryFilters filters={filters} onChange={setFilters} />
      <p className={styles.note}>{RETENTION_NOTE}</p>
      <div className={styles.results}>
        <HistoryTable
          onSelect={setSelected}
          onSort={(key) => {
            setSort(toggleSort(sort, key));
          }}
          rows={history.data.data.items}
          sort={sort}
          timezone={timezone}
        />
        <div className={styles.footer}>
          <p className={styles.note}>{ENTRIES_NOTE}</p>
          <CursorPager nextCursor={history.data.data.cursor} trail={trail} />
        </div>
      </div>
      {selected === undefined ? null : (
        <MessageDrawer
          messageId={selected}
          onClose={() => {
            setSelected(undefined);
          }}
          timezone={timezone}
        />
      )}
    </Panel>
  );
}
