import { Icon } from "@/components/Icon/Icon";
import { GITHUB_URL } from "@/lib/paths";

import { CodeSample } from "./CodeSample";

import styles from "./Developers.module.css";

const EYEBROW = "For developers";
const LEAD =
  "The same account, balance and history as the console, over a REST API with Basic auth.";
const REFERENCE_LABEL = "Read the API reference";
const REFERENCE_URL = `${GITHUB_URL}/blob/main/specs/04-developer-api.md`;
const TITLE = "Send your first SMS with one request";
const POINTS = [
  "Up to 1,000 messages in one call, all or nothing",
  "Schedule any message up to 90 days ahead",
  "Signed webhooks for delivery reports and replies",
] as const;

export function Developers() {
  return (
    <section className={styles.developers} id="developers">
      <div className={styles.inner}>
        <div className={styles.copy}>
          <span className={styles.eyebrow}>{EYEBROW}</span>
          <h2 className={styles.title}>{TITLE}</h2>
          <p className={styles.lead}>{LEAD}</p>
          <ul className={styles.points}>
            {POINTS.map((point) => (
              <li className={styles.point} key={point}>
                <span className={styles.tick}>
                  <Icon name="check" size={14} />
                </span>
                {point}
              </li>
            ))}
          </ul>
          <a className={styles.reference} href={REFERENCE_URL} rel="noopener" target="_blank">
            {REFERENCE_LABEL}
          </a>
        </div>
        <CodeSample />
      </div>
    </section>
  );
}
