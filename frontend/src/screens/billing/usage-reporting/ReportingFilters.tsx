import type { UserRow } from "@/api/generated/dashboard";
import { Input } from "@/components/Input/Input";
import { Select } from "@/components/Select/Select";

import { PRODUCT_OPTIONS, productFilterOf, userOptions } from "../rules";
import type { ReportingFilterState } from "./rules";

import styles from "./ReportingFilters.module.css";

const COUNTRY_HELPER = "ISO code, e.g. GB";
const COUNTRY_LABEL = "Countries";
const PRODUCTS_LABEL = "Products";
const SENDER_HELPER = "Exact sender ID";
const SENDER_LABEL = "Sender IDs";
const SINCE_LABEL = "From";
const SUBACCOUNTS_LABEL = "Subaccounts";
const UNTIL_LABEL = "To";

interface Props {
  filters: ReportingFilterState;
  onChange: (filters: ReportingFilterState) => void;
  users: readonly UserRow[];
}

export function ReportingFilters({ filters, onChange, users }: Props) {
  return (
    <div className={styles.filters}>
      <Input
        id="reporting-since"
        label={SINCE_LABEL}
        onChange={(event) => {
          onChange({ ...filters, since: event.target.value });
        }}
        type="date"
        value={filters.since}
      />
      <Input
        id="reporting-until"
        label={UNTIL_LABEL}
        onChange={(event) => {
          onChange({ ...filters, until: event.target.value });
        }}
        type="date"
        value={filters.until}
      />
      <Select
        id="reporting-products"
        label={PRODUCTS_LABEL}
        onChange={(event) => {
          onChange({ ...filters, products: productFilterOf(event.target.value) });
        }}
        options={PRODUCT_OPTIONS}
        value={filters.products}
      />
      <Select
        id="reporting-subaccounts"
        label={SUBACCOUNTS_LABEL}
        onChange={(event) => {
          onChange({ ...filters, userIds: event.target.value });
        }}
        options={userOptions(users)}
        value={filters.userIds}
      />
      <Input
        helper={SENDER_HELPER}
        id="reporting-sender"
        label={SENDER_LABEL}
        onChange={(event) => {
          onChange({ ...filters, senderIds: event.target.value });
        }}
        value={filters.senderIds}
      />
      <Input
        helper={COUNTRY_HELPER}
        id="reporting-country"
        label={COUNTRY_LABEL}
        onChange={(event) => {
          onChange({ ...filters, countries: event.target.value });
        }}
        value={filters.countries}
      />
    </div>
  );
}
