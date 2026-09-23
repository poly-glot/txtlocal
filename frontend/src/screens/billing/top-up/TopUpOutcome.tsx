import { useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";

import { invalidate, useApiQuery } from "@/api/queries";
import { Money } from "@/components/Money/Money";

import { isPendingTopUp } from "./rules";

import styles from "./TopUpOutcome.module.css";

const CREDITED_SUFFIX = "credited to your balance.";
const EXPIRED_MSG = "This top-up has expired. Try again.";
const PENDING_MSG = "Waiting for payment to confirm…";
const POLL_MS = 2_000;
const TROUBLE_MSG = "We could not confirm this top-up. Refresh to check again.";

const PAID_STALES = [
  "get /api/app/billing/summary",
  "get /api/app/home",
  "get /api/app/me",
] as const;

interface Props {
  topUpId: string;
}

export function TopUpOutcome({ topUpId }: Props) {
  const queryClient = useQueryClient();
  const outcome = useApiQuery(
    "get",
    "/api/app/billing/top-ups/{top_up_id}",
    { params: { path: { top_up_id: topUpId } } },
    { refetchInterval: (query) => (isPendingTopUp(query.state.data) ? POLL_MS : false) },
  );
  const status = outcome.data?.status === "OK" ? outcome.data.data.status : undefined;

  useEffect(() => {
    if (status === "PAID") {
      invalidate(queryClient, PAID_STALES);
    }
  }, [queryClient, status]);

  if (outcome.data === undefined) {
    return (
      <p className={styles.outcome} role="status">
        {PENDING_MSG}
      </p>
    );
  }
  if (outcome.data.status === "ERROR") {
    return (
      <p className={styles.outcome} data-tone="error" role="alert">
        {outcome.data.message}
      </p>
    );
  }

  const view = outcome.data.data;
  if (view.status === "PENDING") {
    return (
      <p className={styles.outcome} role="status">
        {PENDING_MSG}
      </p>
    );
  }
  if (view.status === "EXPIRED") {
    return (
      <p className={styles.outcome} data-tone="error" role="alert">
        {EXPIRED_MSG}
      </p>
    );
  }

  const credited = view.creditedMicro;
  if (typeof credited !== "number") {
    return (
      <p className={styles.outcome} data-tone="error" role="alert">
        {TROUBLE_MSG}
      </p>
    );
  }

  return (
    <p className={styles.outcome} data-tone="success" role="status">
      <Money micro={credited} /> {CREDITED_SUFFIX}
    </p>
  );
}
