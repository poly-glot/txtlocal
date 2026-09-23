import type { Notice, Result } from "@/types";

export function noticeOf(result: Result<unknown>, successMessage: string): Notice {
  return result.status === "OK"
    ? { message: successMessage, tone: "success" }
    : { message: result.message, tone: "error" };
}

export function refusalNotice(result: Result<unknown>): Notice | undefined {
  return result.status === "ERROR" ? { message: result.message, tone: "error" } : undefined;
}

export function undismissedRefusalNotice(
  result: Result<unknown>,
  dismissedAt: number,
  updatedAt: number,
): Notice | undefined {
  return updatedAt === dismissedAt ? undefined : refusalNotice(result);
}
