import { useState } from "react";

import type { ContactList } from "@/api/generated/dashboard";
import { useApiMutation } from "@/api/queries";
import { Toast } from "@/components/Toast/Toast";
import { saveCsv } from "@/lib/download";
import { refusalNotice } from "@/lib/notice";
import type { Notice, Result } from "@/types";

import { DELETE_ACTION, ListCard, RENAME_ACTION } from "./ListCard";
import { csvName } from "./rules";

import styles from "./ListCards.module.css";

const EMPTY_MSG = "No lists found.";

interface Props {
  label: string;
  lists: readonly ContactList[];
  onRename: (list: ContactList) => void;
  onSelect: (listId: string) => void;
  selected: ContactList | undefined;
}

export function ListCards({ label, lists, onRename, onSelect, selected }: Props) {
  const [notice, setNotice] = useState<Notice>();
  const remove = useApiMutation("delete", "/api/app/lists/{listId}");
  const download = useApiMutation("get", "/api/app/lists/{listId}/export");

  const refuse = (result: Result<unknown>) => {
    setNotice((current) => refusalNotice(result) ?? current);
  };

  const act = (list: ContactList, action: string) => {
    if (action === RENAME_ACTION) {
      onRename(list);
      return;
    }
    if (action === DELETE_ACTION) {
      remove.mutate({ params: { path: { listId: list.listId } } }, { onSuccess: refuse });
      return;
    }
    download.mutate(
      { params: { path: { listId: list.listId } }, parseAs: "text" },
      {
        onSuccess: (result) => {
          refuse(result);
          if (result.status === "OK") {
            saveCsv(result.data, csvName(list));
          }
        },
      },
    );
  };

  return (
    <div className={styles.cards}>
      {lists.length === 0 ? <p className={styles.empty}>{EMPTY_MSG}</p> : null}
      <ul aria-label={label} className={styles.list} hidden={lists.length === 0}>
        {lists.map((list) => (
          <ListCard
            active={list.listId === selected?.listId}
            key={list.listId}
            list={list}
            onOpen={() => {
              onSelect(list.listId);
            }}
            onPick={(action) => {
              act(list, action);
            }}
          />
        ))}
      </ul>
      <Toast
        notice={notice}
        onDismiss={() => {
          setNotice(undefined);
        }}
      />
    </div>
  );
}
