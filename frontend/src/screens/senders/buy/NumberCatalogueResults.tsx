import type { CatalogueNumber, paths } from "@/api/generated/dashboard";
import { useApiQuery } from "@/api/queries";
import { Panel } from "@/components/Panel/Panel";
import { StatusPanel } from "@/components/StatusPanel/StatusPanel";

import { NumberCatalogueTable } from "./NumberCatalogueTable";

const TITLE = "Available numbers";

type NumberSearchQuery = NonNullable<paths["/api/app/numbers"]["get"]["parameters"]["query"]>;

interface Props {
  onBuy: (number: CatalogueNumber) => void;
  onPage: (page: number) => void;
  query: NumberSearchQuery;
}

export function NumberCatalogueResults({ onBuy, onPage, query }: Props) {
  const catalogue = useApiQuery("get", "/api/app/numbers", { params: { query } });

  if (catalogue.data === undefined) {
    return <StatusPanel title={TITLE} />;
  }
  if (catalogue.data.status === "ERROR") {
    return <StatusPanel error={catalogue.data.message} title={TITLE} />;
  }

  const { numbers, page, totalPages } = catalogue.data.data;

  return (
    <Panel title={TITLE}>
      <NumberCatalogueTable
        onBuy={onBuy}
        onPage={onPage}
        page={page}
        rows={numbers}
        totalPages={totalPages}
      />
    </Panel>
  );
}
