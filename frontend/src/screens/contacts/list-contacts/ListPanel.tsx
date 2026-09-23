import { keepPreviousData } from "@tanstack/react-query";
import { useState } from "react";

import type { ContactList } from "@/api/generated/dashboard";
import { useApiQuery } from "@/api/queries";
import { CursorPager } from "@/components/CursorPager/CursorPager";
import { EntriesSelect } from "@/components/EntriesSelect/EntriesSelect";
import { ENTRY_SIZES } from "@/components/EntriesSelect/entrySizes";
import { Panel } from "@/components/Panel/Panel";
import { SearchForm } from "@/components/SearchForm/SearchForm";
import { StatusPanel } from "@/components/StatusPanel/StatusPanel";
import { Toast } from "@/components/Toast/Toast";
import { useAccountTimezone } from "@/lib/useAccountTimezone";
import { useCursorTrail } from "@/lib/useCursorTrail";
import type { Notice } from "@/types";

import { ContactModal } from "./ContactModal";
import { ListActions } from "./ListActions";
import { SelectableContacts } from "./SelectableContacts";
import type { ContactEdit } from "./rules";
import { editOf, newContact } from "./rules";

import styles from "./ListPanel.module.css";

const SEARCH_LABEL = "Search contacts";

interface Props {
  list: ContactList;
}

export function ListPanel({ list }: Props) {
  const [q, setQ] = useState("");
  const [limit, setLimit] = useState<number>(ENTRY_SIZES[0]);
  const [editing, setEditing] = useState<ContactEdit>();
  const [notice, setNotice] = useState<Notice>();
  const trail = useCursorTrail(`${list.listId}|${q}|${String(limit)}`);
  const page = useApiQuery(
    "get",
    "/api/app/lists/{listId}/contacts",
    {
      params: { path: { listId: list.listId }, query: { cursor: trail.cursor ?? null, limit, q } },
    },
    { placeholderData: keepPreviousData },
  );
  const timezone = useAccountTimezone();

  if (page.data === undefined) {
    return <StatusPanel />;
  }
  if (page.data.status === "ERROR") {
    return <StatusPanel error={page.data.message} />;
  }

  const { cursor: nextCursor, items } = page.data.data;

  const actions = (
    <ListActions
      list={list}
      onAdd={() => {
        setEditing(newContact());
      }}
      onNotice={setNotice}
    />
  );

  return (
    <Panel actions={actions} title={list.name}>
      <div className={styles.body}>
        <SearchForm id="contacts-search" label={SEARCH_LABEL} onSearch={setQ} />
        <SelectableContacts
          listId={list.listId}
          onEdit={(contact) => {
            setEditing(editOf(contact));
          }}
          onNotice={setNotice}
          rows={items}
          timezone={timezone}
        />
        <div className={styles.footer}>
          <EntriesSelect id="contacts-entries" onChange={setLimit} value={limit} />
          <CursorPager nextCursor={nextCursor} trail={trail} />
        </div>
        <Toast
          notice={notice}
          onDismiss={() => {
            setNotice(undefined);
          }}
        />
      </div>
      {editing === undefined ? null : (
        <ContactModal
          edit={editing}
          listId={list.listId}
          onClose={() => {
            setEditing(undefined);
          }}
        />
      )}
    </Panel>
  );
}
