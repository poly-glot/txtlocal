import { GITHUB_URL } from "@/lib/paths";

import { Brand } from "./Brand";
import { LANDING_SECTIONS } from "./sections";

import styles from "./LandingFooter.module.css";

const GITHUB_LABEL = "GitHub";
const ISSUES_LABEL = "Report an issue";
const NAV_LABEL = "Footer";
const TAGLINE = "Business SMS on AWS Lambda, built in the open.";

export function LandingFooter() {
  return (
    <footer className={styles.footer}>
      <div className={styles.inner}>
        <div className={styles.about}>
          <Brand />
          <p className={styles.tagline}>{TAGLINE}</p>
        </div>
        <nav aria-label={NAV_LABEL} className={styles.links}>
          {LANDING_SECTIONS.map((section) => (
            <a className={styles.link} href={section.href} key={section.href}>
              {section.label}
            </a>
          ))}
          <a className={styles.link} href={GITHUB_URL} rel="noopener" target="_blank">
            {GITHUB_LABEL}
          </a>
          <a className={styles.link} href={`${GITHUB_URL}/issues`} rel="noopener" target="_blank">
            {ISSUES_LABEL}
          </a>
        </nav>
      </div>
    </footer>
  );
}
