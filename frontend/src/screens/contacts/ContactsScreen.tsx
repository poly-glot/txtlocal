import { keepPreviousData } from "@tanstack/react-query";
import { useState } from "react";

import { useApiQuery } from "@/api/queries";
import { StatusPanel } from "@/components/StatusPanel/StatusPanel";

import { ListPanel } from "./list-contacts/ListPanel";
import { ListsPanel } from "./lists/ListsPanel";

import styles from "./ContactsScreen.module.css";

export function ContactsScreen() {
  const [q, setQ] = useState("");
  const [chosenId, setChosenId] = useState<string>();
  const lists = useApiQuery(
    "get",
    "/api/app/lists",
    { params: { query: { q: q } } },
    { placeholderData: keepPreviousData },
  );

  if (lists.data === undefined) {
    return <StatusPanel />;
  }
  if (lists.data.status === "ERROR") {
    return <StatusPanel error={lists.data.message} />;
  }

  const rows = lists.data.data;
  const selected = rows.find((one) => one.listId === chosenId) ?? rows[0];

  return (
    <div className={styles.panels}>
      <ListsPanel lists={rows} onSearch={setQ} onSelect={setChosenId} selected={selected} />
      {selected === undefined ? null : <ListPanel key={selected.listId} list={selected} />}
    </div>
  );
}
