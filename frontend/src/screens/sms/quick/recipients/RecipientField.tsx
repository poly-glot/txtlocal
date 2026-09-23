import { useEffect, useRef, useState } from "react";
import type { KeyboardEvent } from "react";
import { useSearchParams } from "react-router";

import { useApiQuery } from "@/api/queries";
import { dataOf } from "@/lib/format";
import type { Notice } from "@/types";

import type { Recipient } from "../rules";
import { RecipientSuggestions } from "./RecipientSuggestions";
import { addRecipient, listById, listRecipient, sendableLists, withoutRecipient } from "./rules";

import styles from "./RecipientField.module.css";

const LIST_PARAM = "listId";
const TO_LABEL = "To";
const TO_PLACEHOLDER = "Search Contact/List or enter Mobile number";

const removeLabel = (label: string) => `Remove ${label}`;

interface Props {
  onChange: (recipients: Recipient[]) => void;
  onRefusal: (notice: Notice) => void;
  recipients: readonly Recipient[];
}

export function RecipientField({ onChange, onRefusal, recipients }: Props) {
  const [entry, setEntry] = useState("");
  const seeded = useRef(false);
  const [searchParams] = useSearchParams();
  const lists = dataOf(useApiQuery("get", "/api/app/lists").data, []);
  const seed = listById(lists, searchParams.get(LIST_PARAM));

  const add = (recipient: Recipient) => {
    const added = addRecipient(recipients, recipient);
    if (added.status === "ERROR") {
      onRefusal({ message: added.message, tone: "error" });
      return;
    }
    onChange(added.data);
    setEntry("");
  };

  const addTyped = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key !== "Enter" || entry.trim() === "") {
      return;
    }
    event.preventDefault();
    add({ kind: "NUMBER", label: entry.trim(), value: entry.trim() });
  };

  useEffect(() => {
    if (seeded.current || seed === undefined) {
      return;
    }
    seeded.current = true;
    onChange([...recipients, listRecipient(seed)]);
  }, [onChange, recipients, seed]);

  return (
    <div className={styles.field}>
      <label className={styles.label} htmlFor="quick-to">
        {TO_LABEL}
      </label>
      <ul className={styles.chips}>
        {recipients.map((chip) => (
          <li className={styles.chip} data-kind={chip.kind} key={chip.value}>
            {chip.label}
            <button
              aria-label={removeLabel(chip.label)}
              className={styles.remove}
              onClick={() => {
                onChange(withoutRecipient(recipients, chip.value));
              }}
              type="button"
            >
              ×
            </button>
          </li>
        ))}
      </ul>
      <input
        className={styles.input}
        id="quick-to"
        onChange={(event) => {
          setEntry(event.target.value);
        }}
        onKeyDown={addTyped}
        placeholder={TO_PLACEHOLDER}
        value={entry}
      />
      <RecipientSuggestions
        lists={entry === "" ? [] : sendableLists(lists, entry)}
        onPick={add}
        q={entry}
      />
    </div>
  );
}
