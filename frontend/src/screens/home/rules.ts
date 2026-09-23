import type { QuickSendRequest, QuickSendResult } from "@/api/generated/dashboard";
import { noticeOf } from "@/lib/notice";
import type { Encoding, Segments } from "@/rules/segments";
import { GSM_PART, MAX_PARTS, UCS2_PART } from "@/rules/segments";
import type { Notice, Result } from "@/types";

export const TEST_SENT_MSG = "Test message sent.";

export function recipientsOf(text: string): string[] {
  return text
    .split(",")
    .map((entry) => entry.trim())
    .filter((entry) => entry !== "");
}

export function testSendNotice(result: Result<QuickSendResult>): Notice {
  if (result.status === "ERROR" || result.data.refused.length === 0) {
    return noticeOf(result, TEST_SENT_MSG);
  }

  return { message: result.data.refused.map((entry) => entry.message).join(" "), tone: "error" };
}

export function testSendRequest(body: string, to: string[]): QuickSendRequest {
  return { body, kind: "SMS", messageType: "PROMOTIONAL", shortenUrls: false, subject: "", to };
}

export function capacityOf(encoding: Encoding): number {
  return MAX_PARTS * (encoding === "GSM-7" ? GSM_PART : UCS2_PART);
}

export function counterText(segments: Segments): string {
  return `${String(segments.length)} / ${String(capacityOf(segments.encoding))}`;
}
