import { Link } from "react-router";

import type { CampaignQuote } from "@/api/generated/dashboard";
import { Money } from "@/components/Money/Money";

import { scheduleLabel } from "./rules";

import styles from "./QuoteSummary.module.css";

const COST_LABEL = "Cost:";
const COST_PLACES = 4;
const COUNTRY_LINK = "your country";
const COUNTRY_PATH = "/account/messaging";
const DATE_LABEL = "Date:";
const FROM_LABEL = "From:";
const RECIPIENTS_LABEL = "Total Recipients:";
const REPLIES_NOTE_END = ".";
const REPLIES_NOTE_START = "Replies will return to your txtlocal account if supported in ";

interface Props {
  quote: CampaignQuote;
  sendAt: string;
  timezone: string | undefined;
}

export function QuoteSummary({ quote, sendAt, timezone }: Props) {
  return (
    <dl className={styles.summary}>
      <div className={styles.row}>
        <dt className={styles.term}>{FROM_LABEL}</dt>
        <dd className={styles.value}>{quote.senderDisplay}</dd>
        <dd className={styles.note}>
          {REPLIES_NOTE_START}
          <Link to={COUNTRY_PATH}>{COUNTRY_LINK}</Link>
          {REPLIES_NOTE_END}
        </dd>
      </div>
      <div className={styles.row}>
        <dt className={styles.term}>{RECIPIENTS_LABEL}</dt>
        <dd className={styles.value}>{quote.recipients}</dd>
      </div>
      <div className={styles.row}>
        <dt className={styles.term}>{DATE_LABEL}</dt>
        <dd className={styles.value}>{scheduleLabel(sendAt, new Date(), timezone)}</dd>
      </div>
      <div className={styles.total}>
        <dt className={styles.term}>{COST_LABEL}</dt>
        <dd className={styles.cost}>
          <Money micro={quote.costMicro} places={COST_PLACES} />
        </dd>
      </div>
    </dl>
  );
}
