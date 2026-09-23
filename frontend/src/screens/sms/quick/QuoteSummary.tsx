import type { QuickQuote } from "@/api/generated/dashboard";
import { Money } from "@/components/Money/Money";
import type { Result } from "@/types";

import { LOADING_MSG } from "../rules";
import { deliverLabel, skippedSummary } from "./rules";

import styles from "./QuoteSummary.module.css";

const COST_LABEL = "Cost deducted:";
const COST_PLACES = 4;
const DELIVER_LABEL = "Deliver:";
const RECIPIENTS_LABEL = "Recipients:";

interface Props {
  quote: Result<QuickQuote> | undefined;
  sendAt: string;
  timezone: string | undefined;
}

export function QuoteSummary({ quote, sendAt, timezone }: Props) {
  if (quote === undefined) {
    return <p className={styles.note}>{LOADING_MSG}</p>;
  }
  if (quote.status === "ERROR") {
    return (
      <p className={styles.note} role="alert">
        {quote.message}
      </p>
    );
  }

  const skipped = skippedSummary(quote.data.refused);

  return (
    <div className={styles.summary}>
      <dl className={styles.rows}>
        <dt className={styles.term}>{RECIPIENTS_LABEL}</dt>
        <dd className={styles.value}>{quote.data.recipients}</dd>
        <dt className={styles.term}>{DELIVER_LABEL}</dt>
        <dd className={styles.value}>{deliverLabel(sendAt, timezone)}</dd>
        <dt className={styles.term}>{COST_LABEL}</dt>
        <dd className={styles.value}>
          <Money micro={quote.data.costMicro} places={COST_PLACES} />
        </dd>
      </dl>
      {skipped === undefined ? null : <p className={styles.note}>{skipped}</p>}
      {quote.data.refused.map((refusal) => (
        <p className={styles.note} key={refusal.to}>
          {refusal.message}
        </p>
      ))}
    </div>
  );
}
