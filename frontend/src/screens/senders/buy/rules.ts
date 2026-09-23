import type { UseFor } from "@/api/generated/dashboard";
import type { Option } from "@/components/Select/Select";

export const USE_FOR_OPTIONS: readonly Option[] = [
  { label: "SMS", value: "SMS" },
  { label: "MMS", value: "MMS" },
  { label: "SMS & MMS", value: "SMS_MMS" },
];

export interface NumberFilters {
  contains: string;
  country: string;
  useFor: UseFor;
}

export const defaultNumberFilters = (country: string): NumberFilters => ({
  contains: "",
  country,
  useFor: "SMS",
});

export function isUseFor(value: string): value is UseFor {
  return USE_FOR_OPTIONS.some((option) => option.value === value);
}

export function pageNumbers(totalPages: number): number[] {
  return Array.from({ length: totalPages }, (_value, index) => index + 1);
}
