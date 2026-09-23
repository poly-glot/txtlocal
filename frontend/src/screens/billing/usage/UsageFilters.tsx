import type { UserRow } from "@/api/generated/dashboard";
import { Input } from "@/components/Input/Input";
import { Select } from "@/components/Select/Select";

import { PRODUCT_OPTIONS, productFilterOf, userOptions } from "../rules";
import type { UsageFilterState } from "./rules";

import styles from "./UsageFilters.module.css";

const MONTH_LABEL = "Month";
const PRODUCT_LABEL = "Product";
const USERNAME_LABEL = "Username";

interface Props {
  filters: UsageFilterState;
  month: string;
  onFiltersChange: (filters: UsageFilterState) => void;
  onMonthChange: (month: string) => void;
  users: readonly UserRow[];
}

export function UsageFilters({ filters, month, onFiltersChange, onMonthChange, users }: Props) {
  return (
    <div className={styles.filters}>
      <Input
        id="usage-month"
        label={MONTH_LABEL}
        onChange={(event) => {
          onMonthChange(event.target.value);
        }}
        type="month"
        value={month}
      />
      <Select
        id="usage-product"
        label={PRODUCT_LABEL}
        onChange={(event) => {
          onFiltersChange({ ...filters, product: productFilterOf(event.target.value) });
        }}
        options={PRODUCT_OPTIONS}
        value={filters.product}
      />
      <Select
        id="usage-username"
        label={USERNAME_LABEL}
        onChange={(event) => {
          onFiltersChange({ ...filters, userId: event.target.value });
        }}
        options={userOptions(users)}
        value={filters.userId}
      />
    </div>
  );
}
