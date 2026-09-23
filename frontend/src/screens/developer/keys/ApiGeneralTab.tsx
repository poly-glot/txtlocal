import { Link } from "react-router";

import { Panel } from "@/components/Panel/Panel";
import { StatusPanel } from "@/components/StatusPanel/StatusPanel";
import { useApiQuery } from "@/api/queries";
import { API_DOCS_PATH } from "@/lib/paths";

import styles from "./ApiGeneralTab.module.css";

const AUTH_LABEL = "Authentication";
const AUTH_SENTENCE = "HTTP Basic with your username and API key";
const BASE_URL_LABEL = "API base URL";
const DOCS_LABEL = "API Documentation";
const RATE_LIMIT_LABEL = "Rate limit";
const TITLE = "General";

const rateLimitText = (perMinute: number) => `${String(perMinute)} requests per minute per key`;

export function ApiGeneralTab() {
  const general = useApiQuery("get", "/api/app/developer/general");

  if (general.data === undefined) {
    return <StatusPanel title={TITLE} />;
  }
  if (general.data.status === "ERROR") {
    return <StatusPanel error={general.data.message} title={TITLE} />;
  }

  const { baseUrl, rateLimitPerMinute } = general.data.data;

  return (
    <Panel title={TITLE}>
      <dl className={styles.rows}>
        <div className={styles.row}>
          <dt className={styles.term}>{BASE_URL_LABEL}</dt>
          <dd className={styles.code}>{baseUrl}</dd>
        </div>
        <div className={styles.row}>
          <dt className={styles.term}>{AUTH_LABEL}</dt>
          <dd className={styles.detail}>{AUTH_SENTENCE}</dd>
        </div>
        <div className={styles.row}>
          <dt className={styles.term}>{DOCS_LABEL}</dt>
          <dd className={styles.detail}>
            <Link to={API_DOCS_PATH}>{DOCS_LABEL}</Link>
          </dd>
        </div>
        <div className={styles.row}>
          <dt className={styles.term}>{RATE_LIMIT_LABEL}</dt>
          <dd className={styles.detail}>{rateLimitText(rateLimitPerMinute)}</dd>
        </div>
      </dl>
    </Panel>
  );
}
