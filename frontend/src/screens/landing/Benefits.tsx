import { Icon } from "@/components/Icon/Icon";

import { ConversationDemo } from "./ConversationDemo";

import styles from "./Benefits.module.css";

const TITLE = "Why teams choose txtlocal";
const BENEFITS = [
  {
    body: "Campaigns skip your opt-out list and carry an unsubscribe link.",
    title: "Opt-outs honoured",
  },
  {
    body: "One rate per country, taken from your balance in pounds.",
    title: "Predictable pricing",
  },
  {
    body: "A low-balance email before credit runs out, and auto recharge if you want it.",
    title: "Never run dry",
  },
  { body: "The console fits desktop, tablet and phone.", title: "Works on every screen" },
  {
    body: "Every line is on GitHub, from the Lambda functions to this page.",
    title: "Built in the open",
  },
] as const;

export function Benefits() {
  return (
    <section className={styles.benefits} id="why-txtlocal">
      <div className={styles.inner}>
        <div className={styles.copy}>
          <h2 className={styles.title}>{TITLE}</h2>
          <ul className={styles.list}>
            {BENEFITS.map((benefit) => (
              <li className={styles.benefit} key={benefit.title}>
                <span className={styles.tick}>
                  <Icon name="check" size={20} />
                </span>
                <span className={styles.text}>
                  <span className={styles.name}>{benefit.title}</span>
                  <span className={styles.body}>{benefit.body}</span>
                </span>
              </li>
            ))}
          </ul>
        </div>
        <ConversationDemo />
      </div>
    </section>
  );
}
