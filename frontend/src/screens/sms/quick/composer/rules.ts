import { segmentsOf } from "@/rules/segments";

const MMS_MAX_CHARS = 1_500;

export function mmsCounterText(body: string): string {
  return `Approx. ${String(segmentsOf(body).length)} characters/${String(MMS_MAX_CHARS)} characters allowed`;
}
