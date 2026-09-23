import type { Option } from "@/components/Select/Select";

export function countryOptions(codes: readonly string[]): Option[] {
  const names = new Intl.DisplayNames(["en-GB"], { type: "region" });

  return codes.map((code) => ({ label: `${code} — ${names.of(code) ?? code}`, value: code }));
}
