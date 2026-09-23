import { Input } from "@/components/Input/Input";
import { Select } from "@/components/Select/Select";

import type { LogsFilterState } from "./rules";
import {
  DATE_RANGE_PRESETS,
  ENDPOINT_OPTIONS,
  STATUS_FILTERS,
  dateRangePresetOf,
  statusFilterOf,
} from "./rules";

import styles from "./LogsFilters.module.css";

const DATE_RANGE_LABEL = "Date Range";
const ENDPOINT_LABEL = "Endpoint";
const FROM_LABEL = "From";
const STATUS_LABEL = "Status";
const SUBACCOUNT_LABEL = "Subaccount";
const SUBACCOUNT_PLACEHOLDER = "User id";
const TO_LABEL = "To";

const statusOptions = STATUS_FILTERS.map((status) => ({ label: status, value: status }));
const dateRangeOptions = DATE_RANGE_PRESETS.map((preset) => ({ label: preset, value: preset }));

interface Props {
  filters: LogsFilterState;
  onChange: (filters: LogsFilterState) => void;
}

export function LogsFilters({ filters, onChange }: Props) {
  return (
    <div className={styles.filters}>
      <Select
        id="logs-status"
        label={STATUS_LABEL}
        onChange={(event) => {
          onChange({ ...filters, status: statusFilterOf(event.target.value) });
        }}
        options={statusOptions}
        value={filters.status}
      />
      <Select
        id="logs-endpoint"
        label={ENDPOINT_LABEL}
        onChange={(event) => {
          onChange({ ...filters, endpoint: event.target.value });
        }}
        options={ENDPOINT_OPTIONS}
        value={filters.endpoint}
      />
      <Input
        id="logs-subaccount"
        label={SUBACCOUNT_LABEL}
        onChange={(event) => {
          onChange({ ...filters, subaccount: event.target.value });
        }}
        placeholder={SUBACCOUNT_PLACEHOLDER}
        value={filters.subaccount}
      />
      <Select
        id="logs-date-range"
        label={DATE_RANGE_LABEL}
        onChange={(event) => {
          onChange({ ...filters, preset: dateRangePresetOf(event.target.value) });
        }}
        options={dateRangeOptions}
        value={filters.preset}
      />
      {filters.preset === "Custom" ? (
        <>
          <Input
            id="logs-since"
            label={FROM_LABEL}
            onChange={(event) => {
              onChange({ ...filters, customFrom: event.target.value });
            }}
            type="datetime-local"
            value={filters.customFrom}
          />
          <Input
            id="logs-until"
            label={TO_LABEL}
            onChange={(event) => {
              onChange({ ...filters, customTo: event.target.value });
            }}
            type="datetime-local"
            value={filters.customTo}
          />
        </>
      ) : null}
    </div>
  );
}
