import { Link } from "react-router";

import type { ContactList } from "@/api/generated/dashboard";
import { useApiMutation } from "@/api/queries";
import { ActionMenu } from "@/components/ActionMenu/ActionMenu";
import { IconButton } from "@/components/IconButton/IconButton";
import type { Notice } from "@/types";

import { actionNotice, isCleanUpAction } from "./rules";

import styles from "./ListActions.module.css";

const ADD_NAME = "Add contact";
const CLEAN_UP_LABEL = "Clean Up";
const GROUP_SMS_LABEL = "Group SMS";
const QUICK_SMS_PATH = "/sms/quick";
const SEND_TO_ALL_LABEL = "Send to All";

const CLEAN_UP_ITEMS = [
  { label: "Remove invalid numbers", value: "INVALID" },
  { label: "Remove opted-out contacts", value: "OPTED_OUT" },
];

const quickSmsFor = (listId: string) => `${QUICK_SMS_PATH}?listId=${encodeURIComponent(listId)}`;

interface Props {
  list: ContactList;
  onAdd: () => void;
  onNotice: (notice: Notice) => void;
}

export function ListActions({ list, onAdd, onNotice }: Props) {
  const cleanUp = useApiMutation("post", "/api/app/lists/{listId}/clean-up");

  return (
    <div className={styles.actions}>
      <IconButton icon="plus" label={ADD_NAME} onClick={onAdd} variant="primary" />
      <Link className={styles.link} data-variant="secondary" to={quickSmsFor(list.listId)}>
        {SEND_TO_ALL_LABEL}
      </Link>
      <Link className={styles.link} data-variant="secondary" to={quickSmsFor(list.listId)}>
        {GROUP_SMS_LABEL}
      </Link>
      <ActionMenu
        items={CLEAN_UP_ITEMS}
        label={CLEAN_UP_LABEL}
        onPick={(value) => {
          if (isCleanUpAction(value)) {
            cleanUp.mutate(
              { body: { action: value }, params: { path: { listId: list.listId } } },
              {
                onSuccess: (result) => {
                  onNotice(actionNotice(result));
                },
              },
            );
          }
        }}
      />
    </div>
  );
}
