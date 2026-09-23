import { useState } from "react";

import type { Contact } from "@/api/generated/dashboard";
import type { Sort } from "@/components/Table/Table";
import { ariaSortOf, sortRows, toggleSort } from "@/components/Table/sort";

import { ContactRow } from "./ContactRow";
import { sortValueOf } from "./rules";

import styles from "./ContactsTable.module.css";

const EMPTY_MSG = "No contacts in this list yet.";
const SELECT_ALL_LABEL = "Select all contacts";

const COLUMNS = [
  { header: "DATE UPDATED", key: "updatedAt" },
  { header: "FIRST NAME", key: "firstName" },
  { header: "LAST NAME", key: "lastName" },
  { header: "MOBILE", key: "mobile" },
  { header: "EMAIL", key: "email" },
  { header: "(CF1)", key: "cf1" },
  { header: "(CF2)", key: "cf2" },
  { header: "(CF3)", key: "cf3" },
  { header: "(CF4)", key: "cf4" },
] as const;

interface Props {
  onEdit: (contact: Contact) => void;
  onToggle: (mobile: string) => void;
  onToggleAll: () => void;
  rows: readonly Contact[];
  selected: ReadonlySet<string>;
  timezone: string | undefined;
}

export function ContactsTable({ onEdit, onToggle, onToggleAll, rows, selected, timezone }: Props) {
  const [sort, setSort] = useState<Sort>({ direction: "desc", key: "updatedAt" });

  if (rows.length === 0) {
    return <p className={styles.empty}>{EMPTY_MSG}</p>;
  }

  return (
    <div className={styles.scroll}>
      <table className={styles.table}>
        <thead>
          <tr>
            <th className={styles.header} scope="col">
              <input
                aria-label={SELECT_ALL_LABEL}
                checked={rows.every((row) => selected.has(row.mobile))}
                onChange={onToggleAll}
                type="checkbox"
              />
            </th>
            {COLUMNS.map((column) => (
              <th
                aria-sort={ariaSortOf(column.key, sort)}
                className={styles.header}
                key={column.key}
                scope="col"
              >
                <button
                  className={styles.sort}
                  onClick={() => {
                    setSort(toggleSort(sort, column.key));
                  }}
                  type="button"
                >
                  {column.header}
                </button>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sortRows(rows, sort, sortValueOf).map((contact) => (
            <ContactRow
              contact={contact}
              key={contact.mobile}
              onEdit={onEdit}
              onToggle={onToggle}
              selected={selected.has(contact.mobile)}
              timezone={timezone}
            />
          ))}
        </tbody>
      </table>
    </div>
  );
}
