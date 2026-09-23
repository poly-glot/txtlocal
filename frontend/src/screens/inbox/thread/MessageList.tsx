import type { MessageRow } from "@/api/generated/dashboard";
import { dateTimeIn } from "@/lib/format";

import { tickOf } from "./rules";

import styles from "./MessageList.module.css";

interface Props {
  messages: readonly MessageRow[];
  timezone: string | undefined;
}

export function MessageList({ messages, timezone }: Props) {
  return (
    <ul className={styles.list}>
      {messages.map((message) => (
        <li className={styles.row} data-direction={message.direction} key={message.messageId}>
          <div className={styles.bubble}>
            <p className={styles.body}>{message.body}</p>
            <p className={styles.meta}>
              {message.direction === "OUT" ? (
                <span aria-hidden="true">{tickOf(message.status)} </span>
              ) : null}
              {dateTimeIn(message.queuedAt, timezone, "short")}
            </p>
          </div>
        </li>
      ))}
    </ul>
  );
}
