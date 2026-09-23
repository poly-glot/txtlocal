import type { InboundRule } from "@/api/generated/dashboard";
import { PhoneNumber } from "@/components/PhoneNumber/PhoneNumber";
import { Table } from "@/components/Table/Table";
import type { Column } from "@/components/Table/Table";

import { EnabledMark } from "../EnabledMark";
import { RuleRowActions } from "../RuleRowActions";
import { actionAddressDisplay, matchForDisplay } from "./rules";

const ANY_LABEL = "Any";
const EMPTY_MSG = "No inbound rules yet.";

interface Props {
  onDelete: (rule: InboundRule) => void;
  onEdit: (rule: InboundRule) => void;
  onToggle: (rule: InboundRule) => void;
  rows: readonly InboundRule[];
}

export function InboundRulesTable({ onDelete, onEdit, onToggle, rows }: Props) {
  return (
    <Table
      columns={columnsFor(onDelete, onEdit, onToggle)}
      emptyText={EMPTY_MSG}
      keyOf={(row) => row.ruleId}
      rows={rows}
    />
  );
}

function columnsFor(
  onDelete: (rule: InboundRule) => void,
  onEdit: (rule: InboundRule) => void,
  onToggle: (rule: InboundRule) => void,
): readonly Column<InboundRule>[] {
  return [
    {
      header: "DEDICATED NUMBER",
      key: "number",
      render: (row) =>
        row.number === null || row.number === undefined ? (
          ANY_LABEL
        ) : (
          <PhoneNumber e164={row.number} />
        ),
    },
    { header: "RULE NAME", key: "name", render: (row) => row.name },
    { header: "ACTION", key: "action", render: (row) => row.action },
    { header: "ACTION ADDRESS", key: "actionAddress", render: (row) => actionAddressDisplay(row) },
    { header: "MATCH FOR", key: "matchFor", render: (row) => matchForDisplay(row) },
    {
      header: "ENABLED",
      key: "enabled",
      render: (row) => <EnabledMark enabled={row.enabled} />,
    },
    {
      header: "",
      key: "rowActions",
      render: (row) => (
        <RuleRowActions
          enabled={row.enabled}
          name={row.name}
          onDelete={() => {
            onDelete(row);
          }}
          onEdit={() => {
            onEdit(row);
          }}
          onToggle={() => {
            onToggle(row);
          }}
        />
      ),
    },
  ];
}
