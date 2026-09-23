import type { SenderView } from "@/api/generated/dashboard";
import { Badge } from "@/components/Badge/Badge";
import { Table } from "@/components/Table/Table";
import type { Column } from "@/components/Table/Table";

import { countryLabel } from "../rules";
import { alphaBadgeTone, labelForUseCase, registeredText } from "./rules";

const EMPTY_MSG = "";

const COLUMNS: readonly Column<SenderView>[] = [
  { header: "Country", key: "country", render: (row) => countryLabel(row.country) },
  { header: "Alpha Tag", key: "tag", render: (row) => row.value },
  {
    header: "Use case",
    key: "useCase",
    render: (row) =>
      row.useCase === undefined || row.useCase === null ? "" : labelForUseCase(row.useCase),
  },
  {
    header: "Status",
    key: "status",
    render: (row) => <Badge tone={alphaBadgeTone(row.status)}>{row.statusLabel}</Badge>,
  },
  { header: "Registered", key: "registered", render: (row) => registeredText(row.createdAt) },
];

interface Props {
  rows: readonly SenderView[];
}

export function AlphaTagsTable({ rows }: Props) {
  return (
    <Table columns={COLUMNS} emptyText={EMPTY_MSG} keyOf={(row) => row.senderId} rows={rows} />
  );
}
