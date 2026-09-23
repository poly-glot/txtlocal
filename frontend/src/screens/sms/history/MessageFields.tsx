import type { MessageRow } from "@/api/generated/dashboard";
import { Money } from "@/components/Money/Money";
import { dateTimeIn } from "@/lib/format";
import type { Result } from "@/types";

import { LOADING_MSG } from "../rules";
import { STATUS_DISPLAY } from "./rules";

import styles from "./MessageFields.module.css";

const PRICE_LABEL = "Price";
const PRICE_PLACES = 4;

interface Props {
  message: Result<MessageRow> | undefined;
  timezone: string | undefined;
}

export function MessageFields({ message, timezone }: Props) {
  if (message === undefined) {
    return <p className={styles.value}>{LOADING_MSG}</p>;
  }
  if (message.status === "ERROR") {
    return (
      <p className={styles.value} role="alert">
        {message.message}
      </p>
    );
  }

  return (
    <dl className={styles.fields}>
      {fieldsOf(message.data, timezone).map((field) => (
        <div className={styles.row} key={field.label}>
          <dt className={styles.term}>{field.label}</dt>
          <dd className={styles.value}>{field.value}</dd>
        </div>
      ))}
      <div className={styles.row}>
        <dt className={styles.term}>{PRICE_LABEL}</dt>
        <dd className={styles.value}>
          <Money micro={message.data.priceMicro} places={PRICE_PLACES} />
        </dd>
      </div>
    </dl>
  );
}

function fieldsOf(row: MessageRow, timezone: string | undefined) {
  return [
    { label: "Date", value: dateTimeIn(row.queuedAt, timezone, "short") },
    { label: "Username", value: row.username },
    { label: "From", value: row.from },
    { label: "To", value: row.to },
    { label: "Status", value: STATUS_DISPLAY[row.status].label },
    { label: "Parts", value: String(row.parts) },
    { label: "Encoding", value: row.encoding },
    { label: "Country", value: row.country },
    { label: "Provider id", value: row.providerMessageId ?? "" },
    { label: "Failure reason", value: row.failureReason ?? "" },
    { label: "Body", value: row.body },
  ];
}
