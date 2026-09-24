import styles from "./ConversationDemo.module.css";

const AGENT_INITIALS = "AK";
const DEMO_LABEL = "Example conversation in the shared inbox";
const INBOUND = "Hi, can I move my appointment to Thursday?";
const OUTBOUND = "Of course. You're booked for Thursday at 10am. See you then!";
const REPLIED_BY = "Amira, front desk · replied in 2 min";
const TITLE = "Messenger";

export function ConversationDemo() {
  return (
    <figure aria-label={DEMO_LABEL} className={styles.card}>
      <span className={styles.title}>{TITLE}</span>
      <p className={styles.inbound}>{INBOUND}</p>
      <p className={styles.outbound}>{OUTBOUND}</p>
      <div className={styles.footer}>
        <span className={styles.avatar}>{AGENT_INITIALS}</span>
        <span className={styles.repliedBy}>{REPLIED_BY}</span>
      </div>
    </figure>
  );
}
