import type { SenderView } from "@/api/generated/dashboard";

import { DATE_FORMAT, DIAL_CODES } from "../rules";

const INTERNATIONAL_PREFIX = "00";

const MIN_NUMBER_DIGITS = 7;

export const CODE_DIGITS = 6;

export const GLOBE = "🌐";

const VERIFICATION_CODE = new RegExp(`^\\d{${String(CODE_DIGITS)}}$`, "u");

export interface OwnNumberDraft {
  code: string;
  country: string;
  nickname: string;
  number: string;
}

const digitsOf = (value: string) => value.replace(/\D/gu, "");

export const isDiallable = (number: string) => digitsOf(number).length >= MIN_NUMBER_DIGITS;

export const isVerificationCode = (code: string) => VERIFICATION_CODE.test(code);

export const emptyOwnNumber = (country: string): OwnNumberDraft => ({
  code: "",
  country,
  nickname: "",
  number: "",
});

export const reverifyDraft = (sender: SenderView): OwnNumberDraft => ({
  code: "",
  country: sender.country,
  nickname: sender.nickname ?? "",
  number: sender.value,
});

export const isAwaitingVerification = (sender: SenderView) =>
  sender.status === "PENDING_VERIFICATION";

export const isCancellableDedicated = (sender: SenderView) =>
  sender.kind === "DEDICATED" && sender.status === "READY" && !sender.cancelled;

export function dedicatedBadgeTone(status: string): "neutral" | "success" | "warning" {
  if (status === "READY") {
    return "success";
  }
  return status === "RELEASED" ? "neutral" : "warning";
}

export function dialled(country: string, number: string): string {
  const digits = digitsOf(number);
  if (number.trim().startsWith("+")) {
    return `+${digits}`;
  }
  if (digits.startsWith(INTERNATIONAL_PREFIX)) {
    return `+${digits.slice(INTERNATIONAL_PREFIX.length)}`;
  }

  return `${DIAL_CODES[country] ?? ""}${digits.replace(/^0/u, "")}`;
}

export function lastVerifiedText(verifiedAt: string | null | undefined): string {
  return typeof verifiedAt === "string" ? DATE_FORMAT.format(new Date(verifiedAt)) : "";
}
