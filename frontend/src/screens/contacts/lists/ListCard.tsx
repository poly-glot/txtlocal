import type { ContactList } from "@/api/generated/dashboard";
import { ActionMenu } from "@/components/ActionMenu/ActionMenu";
import { Badge } from "@/components/Badge/Badge";

import { contactsLabel, isOptOut } from "./rules";

import styles from "./ListCard.module.css";

export const DELETE_ACTION = "Delete";
export const EXPORT_ACTION = "Export";
export const RENAME_ACTION = "Rename";

const OPT_OUT_BADGE = "Opt-out";
const OPT_OUT_ITEMS = [{ label: EXPORT_ACTION, value: EXPORT_ACTION }];
const STANDARD_ITEMS = [
  { label: RENAME_ACTION, value: RENAME_ACTION },
  { label: EXPORT_ACTION, value: EXPORT_ACTION },
  { label: DELETE_ACTION, value: DELETE_ACTION },
];

const menuName = (name: string) => `Actions for ${name}`;

interface Props {
  active: boolean;
  list: ContactList;
  onOpen: () => void;
  onPick: (action: string) => void;
}

export function ListCard({ active, list, onOpen, onPick }: Props) {
  const optOut = isOptOut(list);

  return (
    <li className={styles.row}>
      <button aria-current={active} className={styles.open} onClick={onOpen} type="button">
        <span className={styles.heading}>
          <span className={styles.name}>{list.name}</span>
          {optOut ? <Badge>{OPT_OUT_BADGE}</Badge> : null}
        </span>
        <span className={styles.count}>{contactsLabel(list.contactCount)}</span>
      </button>
      <ActionMenu
        icon="more"
        items={optOut ? OPT_OUT_ITEMS : STANDARD_ITEMS}
        label={menuName(list.name)}
        onPick={onPick}
      />
    </li>
  );
}
