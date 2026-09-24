import { Button } from "@/components/Button/Button";

import styles from "./CallToAction.module.css";

const LEAD = "Create an account, claim your trial credit and send your first message in minutes.";
const START_LABEL = "Start free trial";
const TITLE = "Ready to send your first message?";

interface Props {
  onStart: () => void;
}

export function CallToAction({ onStart }: Props) {
  return (
    <section className={styles.cta}>
      <div className={styles.inner}>
        <div className={styles.panel}>
          <h2 className={styles.title}>{TITLE}</h2>
          <p className={styles.lead}>{LEAD}</p>
          <Button onClick={onStart} variant="secondary">
            {START_LABEL}
          </Button>
        </div>
      </div>
    </section>
  );
}
