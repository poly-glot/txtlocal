import { ActionMenu } from "@/components/ActionMenu/ActionMenu";
import { IconButton } from "@/components/IconButton/IconButton";
import { Select } from "@/components/Select/Select";

import type { StatusFilter } from "./rules";
import { STATUS_OPTIONS, statusFilterOf } from "./rules";

import styles from "./ConversationsToolbar.module.css";

const MARK_ALL_LABEL = "Mark all as read";
const MENU_ITEMS = [{ label: MARK_ALL_LABEL, value: MARK_ALL_LABEL }];
const MENU_LABEL = "More actions";
const NEW_LABEL = "New conversation";
const STATUS_LABEL = "Status";

interface Props {
  onMarkAllRead: () => void;
  onStatusChange: (status: StatusFilter) => void;
  onToggleCompose: () => void;
  status: StatusFilter;
}

export function ConversationsToolbar({
  onMarkAllRead,
  onStatusChange,
  onToggleCompose,
  status,
}: Props) {
  return (
    <div className={styles.toolbar}>
      <IconButton icon="plus" label={NEW_LABEL} onClick={onToggleCompose} variant="primary" />
      <div className={styles.filter}>
        <Select
          id="inbox-status"
          label={STATUS_LABEL}
          labelHidden
          onChange={(event) => {
            onStatusChange(statusFilterOf(event.target.value));
          }}
          options={STATUS_OPTIONS}
          value={status}
        />
      </div>
      <ActionMenu icon="more" items={MENU_ITEMS} label={MENU_LABEL} onPick={onMarkAllRead} />
    </div>
  );
}
