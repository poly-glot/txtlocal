import { Button } from "@/components/Button/Button";
import { Icon } from "@/components/Icon/Icon";
import { GITHUB_URL } from "@/lib/paths";

import { SendDemo } from "./SendDemo";

import styles from "./Hero.module.css";

const BADGE = "Open source · Runs on AWS Lambda";
const HEADLINE_ACCENT = "actually read";
const HEADLINE_LEAD = "Send SMS your customers";
const LEAD =
  "Send one-off texts and campaigns, answer every reply from a shared inbox, and pay only for what you send.";
const SOURCE_LABEL = "View on GitHub";
const START_LABEL = "Start free";
const TRUST = ["£2 trial credit", "No contracts", "Pay as you go"] as const;

interface Props {
  onStart: () => void;
}

export function Hero({ onStart }: Props) {
  return (
    <section className={styles.hero}>
      <div className={styles.inner}>
        <div className={styles.copy}>
          <span className={styles.badge}>
            <span className={styles.pulse} />
            {BADGE}
          </span>
          <h1 className={styles.headline}>
            {HEADLINE_LEAD} <span className={styles.accent}>{HEADLINE_ACCENT}</span>
          </h1>
          <p className={styles.lead}>{LEAD}</p>
          <div className={styles.actions}>
            <Button onClick={onStart}>{START_LABEL}</Button>
            <a
              className={styles.source}
              data-variant="secondary"
              href={GITHUB_URL}
              rel="noopener"
              target="_blank"
            >
              {SOURCE_LABEL}
            </a>
          </div>
          <ul className={styles.trust}>
            {TRUST.map((point) => (
              <li className={styles.point} key={point}>
                <Icon name="check" size={14} />
                {point}
              </li>
            ))}
          </ul>
        </div>
        <SendDemo />
      </div>
    </section>
  );
}
