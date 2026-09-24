import { Icon } from "@/components/Icon/Icon";

import styles from "./Features.module.css";

const LEAD = "Pay as you go in pounds. No contracts and no per-seat fees.";
const TITLE = "Everything a small team needs to text customers";
const FEATURES = [
  {
    body: "Send one message or thousands, straight away or on a schedule.",
    icon: "send",
    title: "Quick SMS and campaigns",
  },
  {
    body: "Replies land in one inbox, threaded by contact, for the whole team.",
    icon: "message",
    title: "Two-way inbox",
  },
  {
    body: "Send as your brand name, or from a dedicated number customers can reply to.",
    icon: "hash",
    title: "Sender IDs and numbers",
  },
  {
    body: "Follow every message from sent to delivered, failed or unreachable.",
    icon: "signal",
    title: "Delivery receipts",
  },
  {
    body: "A REST API and signed webhooks to send and track messages from your own code.",
    icon: "code",
    title: "Developer API",
  },
] as const;

export function Features() {
  return (
    <section className={styles.features} id="product">
      <div className={styles.inner}>
        <div className={styles.heading}>
          <h2 className={styles.title}>{TITLE}</h2>
          <p className={styles.lead}>{LEAD}</p>
        </div>
        <ul className={styles.grid}>
          {FEATURES.map((feature) => (
            <li className={styles.feature} key={feature.title}>
              <span className={styles.icon}>
                <Icon name={feature.icon} size={20} />
              </span>
              <h3 className={styles.name}>{feature.title}</h3>
              <p className={styles.body}>{feature.body}</p>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
