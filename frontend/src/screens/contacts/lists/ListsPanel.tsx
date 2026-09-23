import { useState } from "react";

import type { ContactList } from "@/api/generated/dashboard";
import { ActionMenu } from "@/components/ActionMenu/ActionMenu";
import { Panel } from "@/components/Panel/Panel";
import { SearchForm } from "@/components/SearchForm/SearchForm";

import { ImportModal } from "./ImportModal";
import { ListCards } from "./ListCards";
import { ListModal } from "./ListModal";
import type { ListDraft } from "./rules";
import { newList, renameDraft } from "./rules";

const ADD_NAME = "New list or import contacts";
const IMPORT_VALUE = "Import contacts";
const NEW_VALUE = "New list";
const SEARCH_ID = "lists-search";
const SEARCH_LABEL = "Search lists";
const TITLE = "Lists";

const NEW_ITEMS = [{ label: NEW_VALUE, value: NEW_VALUE }];
const ADD_ITEMS = [...NEW_ITEMS, { label: IMPORT_VALUE, value: IMPORT_VALUE }];

interface Props {
  lists: readonly ContactList[];
  onSearch: (q: string) => void;
  onSelect: (listId: string) => void;
  selected: ContactList | undefined;
}

export function ListsPanel({ lists, onSearch, onSelect, selected }: Props) {
  const [draft, setDraft] = useState<ListDraft>();
  const [importListId, setImportListId] = useState<string>();

  const addMenu = (
    <ActionMenu
      emphasis="primary"
      icon="plus"
      items={selected === undefined ? NEW_ITEMS : ADD_ITEMS}
      label={ADD_NAME}
      onPick={(value) => {
        if (value === NEW_VALUE) {
          setDraft(newList());
          return;
        }
        setImportListId(selected?.listId);
      }}
    />
  );

  return (
    <Panel actions={addMenu} title={TITLE}>
      <SearchForm id={SEARCH_ID} label={SEARCH_LABEL} onSearch={onSearch} />
      <ListCards
        label={TITLE}
        lists={lists}
        onRename={(list) => {
          setDraft(renameDraft(list));
        }}
        onSelect={onSelect}
        selected={selected}
      />
      {draft === undefined ? null : (
        <ListModal
          draft={draft}
          onClose={() => {
            setDraft(undefined);
          }}
          onSaved={(saved) => {
            setDraft(undefined);
            onSelect(saved.listId);
          }}
        />
      )}
      {importListId === undefined ? null : (
        <ImportModal
          listId={importListId}
          onClose={() => {
            setImportListId(undefined);
          }}
        />
      )}
    </Panel>
  );
}
