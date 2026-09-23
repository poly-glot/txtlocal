import type { Option } from "@/components/Select/Select";
import { GSM_PART, GSM_SINGLE, MAX_PARTS } from "@/rules/segments";

export function partsOption(parts: number): Option {
  const characters = parts === 1 ? GSM_SINGLE : parts * GSM_PART;

  return { label: `${String(parts)} = ${String(characters)} characters`, value: String(parts) };
}

export function partsOptions(): Option[] {
  return Array.from({ length: MAX_PARTS }, (_, index) => partsOption(index + 1));
}
