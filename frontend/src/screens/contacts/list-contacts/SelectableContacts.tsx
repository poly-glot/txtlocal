import { useState } from "react";

import type { Contact } from "@/api/generated/dashboard";
import type { Notice } from "@/types";

import { BulkToolbar } from "./BulkToolbar";
import { ContactsTable } from "./ContactsTable";
import { toggledAll, toggledOne } from "./rules";

interface Props {
  listId: string;
  onEdit: (contact: Contact) => void;
  onNotice: (notice: Notice) => void;
  rows: readonly Contact[];
  timezone: string | undefined;
}

export function SelectableContacts({ listId, onEdit, onNotice, rows, timezone }: Props) {
  const [selected, setSelected] = useState<ReadonlySet<string>>(new Set<string>());

  return (
    <>
      {selected.size === 0 ? null : (
        <BulkToolbar
          listId={listId}
          onDone={(done) => {
            onNotice(done);
            setSelected(new Set<string>());
          }}
          selected={selected}
        />
      )}
      <ContactsTable
        onEdit={onEdit}
        onToggle={(mobile) => {
          setSelected(toggledOne(selected, mobile));
        }}
        onToggleAll={() => {
          setSelected(
            toggledAll(
              rows.map((row) => row.mobile),
              selected,
            ),
          );
        }}
        rows={rows}
        selected={selected}
        timezone={timezone}
      />
    </>
  );
}
