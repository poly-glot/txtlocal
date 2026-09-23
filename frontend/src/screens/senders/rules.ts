import type { SenderKind, SenderView, SendersView } from "@/api/generated/dashboard";
import type { Option } from "@/components/Select/Select";

export const DATE_FORMAT = new Intl.DateTimeFormat("en-GB", { dateStyle: "medium" });
export const DIAL_CODES: Readonly<Record<string, string>> = { CA: "+1", GB: "+44", US: "+1" };
const FLAG_OFFSET = 0x1f1a5;

const ISO_CODE_LETTERS = 2;

const REGION_NAMES = new Intl.DisplayNames(["en-GB"], { type: "region" });

const SHARED_NUMBERS_OPTION = "Shared Numbers";

function flagOf(country: string): string {
  if (country.length !== ISO_CODE_LETTERS) {
    return country;
  }

  return String.fromCodePoint(
    country.charCodeAt(0) + FLAG_OFFSET,
    country.charCodeAt(1) + FLAG_OFFSET,
  );
}

export function countryLabel(country: string): string {
  const parts = [flagOf(country), REGION_NAMES.of(country) ?? country, DIAL_CODES[country] ?? ""];

  return parts.filter((part) => part !== "").join(" ");
}

export function countryOptions(codes: readonly string[]): Option[] {
  return codes.map((code) => ({ label: countryLabel(code), value: code }));
}

export function sendersOf(view: SendersView, kind: SenderKind): SenderView[] {
  return view.senders[kind] ?? [];
}

export function enabledCountriesOf(view: SendersView): string[] {
  return [...new Set(sendersOf(view, "SHARED").map((sender) => sender.country))].sort();
}

export function senderOptionsFor(view: SendersView, country: string): Option[] {
  return Object.values(view.senders)
    .flat()
    .filter((sender) => sender.status === "READY" && sender.country === country)
    .map((sender) => ({ label: optionLabelOf(sender), value: sender.senderId }));
}

function optionLabelOf(sender: SenderView): string {
  return sender.kind === "SHARED" ? SHARED_NUMBERS_OPTION : sender.display;
}
