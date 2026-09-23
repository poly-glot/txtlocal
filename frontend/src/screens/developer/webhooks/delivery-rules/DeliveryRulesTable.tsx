import type { DeliveryReportRuleView } from "@/api/generated/dashboard";
import { Table } from "@/components/Table/Table";
import type { Column } from "@/components/Table/Table";

import { EnabledMark } from "../EnabledMark";
import { RuleRowActions } from "../RuleRowActions";
import { DELIVERY_EVENT_OPTIONS } from "./rules";

const EMPTY_MSG = "No delivery report rules yet.";

const eventsLabel = (events: DeliveryReportRuleView["events"]) =>
  DELIVERY_EVENT_OPTIONS.find((option) => option.value === events)?.label ?? events;

interface Props {
  onDelete: (rule: DeliveryReportRuleView) => void;
  onEdit: (rule: DeliveryReportRuleView) => void;
  onToggle: (rule: DeliveryReportRuleView) => void;
  rows: readonly DeliveryReportRuleView[];
}

export function DeliveryRulesTable({ onDelete, onEdit, onToggle, rows }: Props) {
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
  onDelete: (rule: DeliveryReportRuleView) => void,
  onEdit: (rule: DeliveryReportRuleView) => void,
  onToggle: (rule: DeliveryReportRuleView) => void,
): readonly Column<DeliveryReportRuleView>[] {
  return [
    { header: "RULE NAME", key: "name", render: (row) => row.name },
    { header: "URL", key: "url", render: (row) => row.url },
    { header: "EVENTS", key: "events", render: (row) => eventsLabel(row.events) },
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
