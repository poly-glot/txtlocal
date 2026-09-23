import styles from "./EmailSmsFaq.module.css";

const FAQ_ITEMS = [
  "How can I strip email signatures from SMS?",
  "How can I email SMS to contacts group?",
  "Where do replies to my emailed SMS go?",
  "How can I send authenticated email-to-SMS from any email?",
  "How can I send SMS from a generic/shared email?",
] as const;

export function EmailSmsFaq() {
  return (
    <ul className={styles.list}>
      {FAQ_ITEMS.map((item) => (
        <li className={styles.item} key={item}>
          {item}
        </li>
      ))}
    </ul>
  );
}
