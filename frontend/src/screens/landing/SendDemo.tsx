import { Icon } from "@/components/Icon/Icon";

import styles from "./SendDemo.module.css";

const DEMO_LABEL = "Example campaign sending";
const MESSAGE = "Your order #4821 has shipped. Track it: txtlocal.junaid.guru/l/4821";
const RECEIPT = "Delivered to +44 7700 900123 · 0.4s";
const STATUS = "Sending";
const TITLE = "Order updates";
const RECIPIENTS = [
  { initials: "SM", name: "Sarah Mensah", status: "Delivered", tone: "accent" },
  { initials: "JO", name: "James Okafor", status: "Delivered", tone: "brand" },
  { initials: "PK", name: "Priya Kapoor", status: "Sending…", tone: "muted" },
] as const;

export function SendDemo() {
  return (
    <figure aria-label={DEMO_LABEL} className={styles.card}>
      <div className={styles.header}>
        <span className={styles.dot} />
        <span className={styles.title}>{TITLE}</span>
        <span className={styles.status}>{STATUS}</span>
      </div>
      <p className={styles.message}>{MESSAGE}</p>
      <div className={styles.receipt}>
        <span className={styles.tick}>
          <Icon name="check" />
        </span>
        <span className={styles.caption}>{RECEIPT}</span>
      </div>
      <ul className={styles.recipients}>
        {RECIPIENTS.map((recipient) => (
          <li className={styles.recipient} key={recipient.name}>
            <span className={styles.avatar} data-tone={recipient.tone}>
              {recipient.initials}
            </span>
            <span className={styles.name}>{recipient.name}</span>
            <span className={styles.badge} data-delivered={recipient.status === "Delivered"}>
              {recipient.status}
            </span>
          </li>
        ))}
      </ul>
    </figure>
  );
}
