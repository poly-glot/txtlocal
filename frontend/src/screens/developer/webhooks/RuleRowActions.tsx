import { RowAction } from "@/components/RowAction/RowAction";

import styles from "./RuleRowActions.module.css";

const DELETE_LABEL = "Delete";
const DISABLE_LABEL = "Disable";
const EDIT_LABEL = "Edit";
const ENABLE_LABEL = "Enable";

const actionName = (action: string, name: string) => `${action} ${name}`;

interface Props {
  enabled: boolean;
  name: string;
  onDelete: () => void;
  onEdit: () => void;
  onToggle: () => void;
}

export function RuleRowActions({ enabled, name, onDelete, onEdit, onToggle }: Props) {
  const toggleLabel = enabled ? DISABLE_LABEL : ENABLE_LABEL;

  return (
    <span className={styles.actions}>
      <RowAction aria-label={actionName(EDIT_LABEL, name)} onClick={onEdit}>
        {EDIT_LABEL}
      </RowAction>
      <RowAction aria-label={actionName(toggleLabel, name)} onClick={onToggle}>
        {toggleLabel}
      </RowAction>
      <RowAction aria-label={actionName(DELETE_LABEL, name)} onClick={onDelete} tone="danger">
        {DELETE_LABEL}
      </RowAction>
    </span>
  );
}
