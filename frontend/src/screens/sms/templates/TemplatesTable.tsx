import type { Template } from "@/api/generated/dashboard";
import { RowAction } from "@/components/RowAction/RowAction";
import { Table } from "@/components/Table/Table";
import type { Column, Sort } from "@/components/Table/Table";
import { sortRows } from "@/components/Table/sort";

import styles from "./TemplatesTable.module.css";

const BODY_HEADER = "BODY";
const DELETE_LABEL = "Delete";
const EDIT_LABEL = "Edit";
const EMPTY_MSG = "No results";
const NAME_HEADER = "NAME";

const actionName = (action: string, name: string) => `${action} ${name}`;

interface Props {
  onDelete: (template: Template) => void;
  onEdit: (template: Template) => void;
  onSort: (key: string) => void;
  rows: readonly Template[];
  sort: Sort;
}

export function TemplatesTable({ onDelete, onEdit, onSort, rows, sort }: Props) {
  return (
    <Table
      columns={columnsFor(onDelete, onEdit)}
      emptyText={EMPTY_MSG}
      keyOf={(row) => row.templateId}
      onSort={onSort}
      rows={sortRows(rows, sort, valueOf)}
      sort={sort}
    />
  );
}

function columnsFor(
  onDelete: (template: Template) => void,
  onEdit: (template: Template) => void,
): readonly Column<Template>[] {
  return [
    { header: NAME_HEADER, key: "name", render: (row) => row.name },
    {
      header: BODY_HEADER,
      key: "body",
      render: (row) => (
        <span className={styles.body}>
          {row.body}
          <span className={styles.actions}>
            <RowAction
              aria-label={actionName(EDIT_LABEL, row.name)}
              onClick={() => {
                onEdit(row);
              }}
            >
              {EDIT_LABEL}
            </RowAction>
            <RowAction
              aria-label={actionName(DELETE_LABEL, row.name)}
              onClick={() => {
                onDelete(row);
              }}
              tone="danger"
            >
              {DELETE_LABEL}
            </RowAction>
          </span>
        </span>
      ),
    },
  ];
}

function valueOf(row: Template, key: string): string {
  return key === "body" ? row.body : row.name;
}
