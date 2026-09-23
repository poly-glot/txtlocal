import { Link } from "react-router";

import styles from "./GetStarted.module.css";

const INTRO = "Add contacts, set up a sender and send your first campaign.";
const STEPS = [
  { label: "Add contacts", to: "/contacts" },
  { label: "Set up a sender", to: "/senders" },
  { label: "Send a Quick SMS", to: "/sms/quick" },
] as const;

export function GetStarted() {
  return (
    <div className={styles.steps}>
      <p className={styles.intro}>{INTRO}</p>
      <ol className={styles.list}>
        {STEPS.map((step) => (
          <li className={styles.step} key={step.to}>
            <Link to={step.to}>{step.label}</Link>
          </li>
        ))}
      </ol>
    </div>
  );
}
