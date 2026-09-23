import type { UseCase } from "@/api/generated/dashboard";
import type { Option } from "@/components/Select/Select";

import { DATE_FORMAT } from "../rules";

export const ALPHA_TAG_MAX = 11;
const ALPHA_TAG_MIN = 3;

export const USE_CASE_OPTIONS: readonly Option[] = [
  { label: "Marketing", value: "MARKETING" },
  { label: "Notifications", value: "NOTIFICATIONS" },
  { label: "Two-factor authentication", value: "TWO_FACTOR_AUTHENTICATION" },
  { label: "Customer service", value: "CUSTOMER_SERVICE" },
  { label: "Other", value: "OTHER" },
];

const ALPHA_TAG_PATTERN = new RegExp(
  `^[A-Za-z0-9+]{${String(ALPHA_TAG_MIN)},${String(ALPHA_TAG_MAX)}}$`,
  "u",
);

export interface AlphaTagDraft {
  country: string;
  tag: string;
  useCase: UseCase;
}

export const isValidAlphaTag = (tag: string) => ALPHA_TAG_PATTERN.test(tag);

export const emptyAlphaTag = (country: string): AlphaTagDraft => ({
  country,
  tag: "",
  useCase: "MARKETING",
});

export function labelForUseCase(useCase: string): string {
  return USE_CASE_OPTIONS.find((option) => option.value === useCase)?.label ?? useCase;
}

export function isUseCase(value: string): value is UseCase {
  return USE_CASE_OPTIONS.some((option) => option.value === value);
}

export function registeredText(createdAt: string): string {
  return DATE_FORMAT.format(new Date(createdAt));
}

export function alphaBadgeTone(status: string): "danger" | "success" | "warning" {
  if (status === "READY") {
    return "success";
  }
  return status === "REJECTED" ? "danger" : "warning";
}
