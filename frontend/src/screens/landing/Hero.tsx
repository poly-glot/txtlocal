import { Button } from "@/components/Button/Button";
import { GITHUB_URL } from "@/lib/paths";

import { SendDemo } from "./SendDemo";

import styles from "./Hero.module.css";

const EYEBROW = "Business SMS, simplified";
const HEADLINE = "Send SMS your customers actually read";
const LEAD =
  "Send one-off texts and campaigns, answer every reply from a shared inbox, and pay only for what you send.";
const SOURCE_LABEL = "View on GitHub";
const START_LABEL = "Start free";

interface Props {
  onStart: () => void;
}

export function Hero({ onStart }: Props) {
  return (
    <section className={styles.hero}>
      <div className={styles.inner}>
        <div className={styles.copy}>
          <span className={styles.eyebrow}>{EYEBROW}</span>
          <h1 className={styles.headline}>{HEADLINE}</h1>
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
        </div>
        <SendDemo />
      </div>
    </section>
  );
}
