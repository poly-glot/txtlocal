import { useState } from "react";

import type { CatalogueNumber } from "@/api/generated/dashboard";
import { Panel } from "@/components/Panel/Panel";

import { BuyANumberFilters } from "./BuyANumberFilters";
import { BuyNumberConfirmModal } from "./BuyNumberConfirmModal";
import { NumberCatalogueResults } from "./NumberCatalogueResults";
import type { NumberFilters } from "./rules";
import { defaultNumberFilters } from "./rules";

import styles from "./BuyANumberScreen.module.css";

const COPY = "Send messages globally and boost customer recognition with purchased numbers.";
const DEFAULT_COUNTRY = "GB";
const TITLE = "Buy A Number";

export function BuyANumberScreen() {
  const [filters, setFilters] = useState<NumberFilters>(defaultNumberFilters(DEFAULT_COUNTRY));
  const [page, setPage] = useState(1);
  const [buying, setBuying] = useState<CatalogueNumber>();

  const changeFilters = (next: NumberFilters) => {
    setFilters(next);
    setPage(1);
  };

  return (
    <div className={styles.page}>
      <Panel title={TITLE}>
        <div className={styles.search}>
          <p className={styles.copy}>{COPY}</p>
          <BuyANumberFilters filters={filters} onChange={changeFilters} />
        </div>
      </Panel>
      <NumberCatalogueResults onBuy={setBuying} onPage={setPage} query={{ ...filters, page }} />
      {buying === undefined ? null : (
        <BuyNumberConfirmModal
          number={buying}
          onBought={() => {
            setBuying(undefined);
          }}
          onClose={() => {
            setBuying(undefined);
          }}
        />
      )}
    </div>
  );
}
