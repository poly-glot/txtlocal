import type { TopUpStatusView } from "@/api/generated/dashboard";
import type { Result } from "@/types";

import { countryNameOf } from "../rules";

const COUNT_FORMAT = new Intl.NumberFormat("en-GB");

export const PER_SMS = "/ SMS";

export function estimateText(estimate: number, country: string): string {
  return `~ ${COUNT_FORMAT.format(estimate)} SMS to ${countryNameOf(country) ?? country}`;
}

export function autoRechargeText(autoRecharge: boolean): string {
  return `Auto Recharge ${autoRecharge ? "ON" : "OFF"}`;
}

export function savingsText(savingsPct: number): string {
  return `Save ${String(savingsPct)}%`;
}

export function isPendingTopUp(outcome: Result<TopUpStatusView> | undefined): boolean {
  return outcome?.status === "OK" && outcome.data.status === "PENDING";
}
