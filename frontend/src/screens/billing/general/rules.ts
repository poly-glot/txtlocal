import type { Option } from "@/components/Select/Select";

import { priceText } from "../rules";

export const RECHARGE_AMOUNT_OPTIONS: readonly Option[] = [
  { label: "£10", value: "10000000" },
  { label: "£30", value: "30000000" },
  { label: "£50", value: "50000000" },
  { label: "£100", value: "100000000" },
];

export const BALANCE_THRESHOLD_OPTIONS: readonly Option[] = [
  { label: "£5.00", value: "5000000" },
  { label: "£10.00", value: "10000000" },
  { label: "£20.00", value: "20000000" },
  { label: "£50.00", value: "50000000" },
];

export function optionsWithSaved(
  options: readonly Option[],
  savedMicro: number,
): readonly Option[] {
  const saved = String(savedMicro);

  if (options.some((option) => option.value === saved)) {
    return options;
  }

  return [...options, { label: `£${priceText(savedMicro)}`, value: saved }].sort(
    (left, right) => Number(left.value) - Number(right.value),
  );
}
