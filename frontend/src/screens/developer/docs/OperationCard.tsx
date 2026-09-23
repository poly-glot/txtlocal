import { Badge } from "@/components/Badge/Badge";
import { Table } from "@/components/Table/Table";
import type { Column } from "@/components/Table/Table";

import type { RenderedOperation, SchemaField } from "./rules";

import styles from "./OperationCard.module.css";

const NO_FIELDS_MSG = "No fields to show.";
const REQUEST_TITLE = "Request body";
const RESPONSE_TITLE = "2xx response";

const FIELD_COLUMNS: readonly Column<SchemaField>[] = [
  { header: "NAME", key: "name", render: (field) => field.name },
  { header: "TYPE", key: "type", render: (field) => field.type },
  { header: "REQUIRED", key: "required", render: (field) => (field.required ? "Yes" : "No") },
];

interface Props {
  operation: RenderedOperation;
}

export function OperationCard({ operation }: Props) {
  return (
    <article className={styles.card}>
      <p className={styles.route}>
        <Badge tone="accent">{operation.method}</Badge>
        <span className={styles.path}>{operation.path}</span>
      </p>
      {operation.summary === undefined ? null : (
        <p className={styles.summary}>{operation.summary}</p>
      )}
      {operation.requestFields === undefined ? null : (
        <FieldsSection
          fields={operation.requestFields}
          note={operation.requestNote}
          title={REQUEST_TITLE}
        />
      )}
      {operation.responseFields === undefined ? null : (
        <FieldsSection
          fields={operation.responseFields}
          note={operation.responseNote}
          title={RESPONSE_TITLE}
        />
      )}
    </article>
  );
}

interface FieldsSectionProps {
  fields: readonly SchemaField[];
  note: string | undefined;
  title: string;
}

function FieldsSection({ fields, note, title }: FieldsSectionProps) {
  return (
    <div className={styles.section}>
      <h3 className={styles.sectionTitle}>{title}</h3>
      <Table
        columns={FIELD_COLUMNS}
        emptyText={note ?? NO_FIELDS_MSG}
        keyOf={(field) => field.name}
        rows={fields}
      />
    </div>
  );
}
