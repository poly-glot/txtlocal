import { Input } from "@/components/Input/Input";
import { Select } from "@/components/Select/Select";
import { COUNTRY_CODES } from "@/rules/countries";

import { countryOptions } from "../rules";
import type { NumberFilters } from "./rules";
import { USE_FOR_OPTIONS, isUseFor } from "./rules";

import styles from "./BuyANumberFilters.module.css";

const CONTAINS_HELPER = "Only show results with these numbers";
const CONTAINS_LABEL = "Filter results";
const CONTAINS_PLACEHOLDER = "eg. 123";
const COUNTRY_HELPER = "What country are your customers in?";
const COUNTRY_LABEL = "Country";
const COUNTRIES = countryOptions(COUNTRY_CODES);
const USE_FOR_HELPER = "What type of messages are you sending?";
const USE_FOR_LABEL = "Use for";

interface Props {
  filters: NumberFilters;
  onChange: (filters: NumberFilters) => void;
}

export function BuyANumberFilters({ filters, onChange }: Props) {
  return (
    <div className={styles.filters}>
      <Select
        helper={COUNTRY_HELPER}
        id="numbers-country"
        label={COUNTRY_LABEL}
        onChange={(event) => {
          onChange({ ...filters, country: event.target.value });
        }}
        options={COUNTRIES}
        value={filters.country}
      />
      <Select
        helper={USE_FOR_HELPER}
        id="numbers-use-for"
        label={USE_FOR_LABEL}
        onChange={(event) => {
          const { value } = event.target;
          if (isUseFor(value)) {
            onChange({ ...filters, useFor: value });
          }
        }}
        options={USE_FOR_OPTIONS}
        value={filters.useFor}
      />
      <Input
        helper={CONTAINS_HELPER}
        id="numbers-contains"
        label={CONTAINS_LABEL}
        onChange={(event) => {
          onChange({ ...filters, contains: event.target.value });
        }}
        placeholder={CONTAINS_PLACEHOLDER}
        value={filters.contains}
      />
    </div>
  );
}
