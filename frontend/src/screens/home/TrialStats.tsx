import { Link } from "react-router";

import { BILLING_TOP_UP_PATH } from "@/lib/paths";

import styles from "./TrialStats.module.css";

const ADD_CREDITS = "Add Credits";
const TRIAL_DAYS_LEFT = "Trial Days Left";

interface Props {
  trialDaysLeft: number;
}

export function TrialStats({ trialDaysLeft }: Props) {
  return (
    <section className={styles.card}>
      <dl className={styles.stat}>
        <dt className={styles.term}>{TRIAL_DAYS_LEFT}</dt>
        <dd className={styles.value}>{trialDaysLeft}</dd>
      </dl>
      <div className={styles.footer}>
        <Link to={BILLING_TOP_UP_PATH}>{ADD_CREDITS}</Link>
      </div>
    </section>
  );
}
