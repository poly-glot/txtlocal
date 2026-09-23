import { useState } from "react";

import { Input } from "@/components/Input/Input";
import { Select } from "@/components/Select/Select";

import { HistoryPresets } from "./HistoryPresets";
import type { HistoryQuery } from "./rules";
import { presetRange } from "./rules";

import styles from "./HistoryFilters.module.css";

const DATE_PLACEHOLDER = "Enter Date";
const FIELD_LABEL = "Field";
const FIELD_OPTIONS = [
  { label: "To", value: "TO" },
  { label: "From", value: "FROM" },
];
const FROM_LABEL = "From";
const SEARCH_LABEL = "Search";
const SEARCH_PLACEHOLDER = "Search in international format";
const TO_LABEL = "To";

interface Props {
  filters: HistoryQuery;
  onChange: (filters: HistoryQuery) => void;
}

export function HistoryFilters({ filters, onChange }: Props) {
  const [search, setSearch] = useState("");

  return (
    <div className={styles.filters}>
      <div className={styles.fields}>
        <Input
          id="history-from"
          label={FROM_LABEL}
          onChange={(event) => {
            onChange({ ...filters, from: event.target.value });
          }}
          placeholder={DATE_PLACEHOLDER}
          type="date"
          value={filters.from ?? ""}
        />
        <Input
          id="history-to"
          label={TO_LABEL}
          onChange={(event) => {
            onChange({ ...filters, to: event.target.value });
          }}
          placeholder={DATE_PLACEHOLDER}
          type="date"
          value={filters.to ?? ""}
        />
        <Select
          id="history-field"
          label={FIELD_LABEL}
          onChange={(event) => {
            onChange({ ...filters, field: event.target.value === "FROM" ? "FROM" : "TO" });
          }}
          options={FIELD_OPTIONS}
          value={filters.field ?? "TO"}
        />
        <form
          className={styles.search}
          onSubmit={(event) => {
            event.preventDefault();
            onChange({ ...filters, q: search });
          }}
          role="search"
        >
          <Input
            id="history-search"
            label={SEARCH_LABEL}
            onChange={(event) => {
              setSearch(event.target.value);
            }}
            placeholder={SEARCH_PLACEHOLDER}
            type="search"
            value={search}
          />
        </form>
      </div>
      <HistoryPresets
        onClear={() => {
          setSearch("");
          onChange(cleared(filters));
        }}
        onPick={(preset) => {
          onChange({ ...filters, ...presetRange(preset, new Date()) });
        }}
      />
    </div>
  );
}

function cleared(filters: HistoryQuery): HistoryQuery {
  const field = filters.field ?? "TO";

  return filters.kind === undefined ? { field } : { field, kind: filters.kind };
}
