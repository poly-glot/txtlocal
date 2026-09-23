import { Select } from "@/components/Select/Select";

import { ENTRY_SIZES } from "./entrySizes";

import styles from "./EntriesSelect.module.css";

const ENTRIES_LABEL = "Entries";
const ENTRIES_NAME = "Show Entries";
const SHOW_LABEL = "Show";
const SIZE_OPTIONS = ENTRY_SIZES.map((size) => ({ label: String(size), value: String(size) }));

interface Props {
  id: string;
  onChange: (limit: number) => void;
  value: number;
}

export function EntriesSelect({ id, onChange, value }: Props) {
  return (
    <div className={styles.entries}>
      <span className={styles.note}>{SHOW_LABEL}</span>
      <Select
        id={id}
        label={ENTRIES_NAME}
        labelHidden
        onChange={(event) => {
          onChange(Number(event.target.value));
        }}
        options={SIZE_OPTIONS}
        value={String(value)}
      />
      <span className={styles.note}>{ENTRIES_LABEL}</span>
    </div>
  );
}
