import type { Product, UserRow } from "@/api/generated/dashboard";
import type { Option } from "@/components/Select/Select";

const MICRO_PER_POUND = 1_000_000;
const PRICE_FORMAT = new Intl.NumberFormat("en-GB", {
  maximumFractionDigits: 4,
  minimumFractionDigits: 2,
  useGrouping: false,
});

const REGION_NAMES = new Intl.DisplayNames(["en"], { type: "region" });
const SORT_PAD_WIDTH = 12;

export const PRODUCT_OPTIONS: readonly Option[] = [
  { label: "All products", value: "" },
  { label: "SMS", value: "SMS" },
  { label: "MMS", value: "MMS" },
  { label: "MMS as link", value: "MMS_AS_LINK" },
];

export function productFilterOf(value: string): Product | "" {
  return value === "SMS" || value === "MMS" || value === "MMS_AS_LINK" ? value : "";
}

export function productLabel(product: Product): string {
  return product === "MMS_AS_LINK" ? "SMS" : product;
}

export function usernameLookup(users: readonly UserRow[]): Map<string, string> {
  return new Map(users.map((user) => [user.userId, user.username]));
}

export function usernameOf(lookup: ReadonlyMap<string, string>, userId: string): string {
  return lookup.get(userId) ?? userId;
}

export function userOptions(users: readonly UserRow[]): Option[] {
  const sorted = [...users].sort((left, right) => left.username.localeCompare(right.username));

  return [
    { label: "All subaccounts", value: "" },
    ...sorted.map((user) => ({ label: user.username, value: user.userId })),
  ];
}

export function numericSortKey(value: number): string {
  return String(value).padStart(SORT_PAD_WIDTH, "0");
}

export function countryNameOf(iso: string): string | undefined {
  try {
    return REGION_NAMES.of(iso);
  } catch {
    return undefined;
  }
}

export function priceText(micro: number): string {
  return PRICE_FORMAT.format(micro / MICRO_PER_POUND);
}
