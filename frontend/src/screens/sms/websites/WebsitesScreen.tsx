import { useState } from "react";

import { useApiQuery } from "@/api/queries";
import { Button } from "@/components/Button/Button";
import { Panel } from "@/components/Panel/Panel";
import { StatusPanel } from "@/components/StatusPanel/StatusPanel";

import { RegisterWebsiteModal } from "./RegisterWebsiteModal";
import { WebsitesTable } from "./WebsitesTable";

import styles from "./WebsitesScreen.module.css";

const ADD_ANOTHER_LABEL = "+ Register a website";
const CARD_COPY =
  "Register websites and subdomains, not single webpages (URLs). Ie: Once you have registered " +
  "txtlocal.com, you don't need to register txtlocal.com/about.";
const EMPTY_COPY =
  "If you're adding a link to messages for the first time, we need to review your website for " +
  "safety. Speed up delivery by registering websites before you send messages with links.";
const EMPTY_TITLE = "Register websites for speedy delivery";
const HEADING = "Registered websites";
const LEARN_MORE_LABEL = "Learn about website registration";
const REGISTER_LABEL = "Register a website";

export function WebsitesScreen() {
  const [registering, setRegistering] = useState(false);
  const websites = useApiQuery("get", "/api/app/websites");

  if (websites.data === undefined) {
    return <StatusPanel title={HEADING} />;
  }
  if (websites.data.status === "ERROR") {
    return <StatusPanel error={websites.data.message} title={HEADING} />;
  }

  const rows = websites.data.data;
  const isEmpty = rows.length === 0;
  const openRegister = () => {
    setRegistering(true);
  };

  const addAnother = isEmpty ? null : <Button onClick={openRegister}>{ADD_ANOTHER_LABEL}</Button>;

  return (
    <Panel actions={addAnother} title={HEADING}>
      <p className={styles.copy}>{CARD_COPY}</p>
      {isEmpty ? (
        <div className={styles.empty}>
          <h3 className={styles.emptyTitle}>{EMPTY_TITLE}</h3>
          <p className={styles.copy}>{EMPTY_COPY}</p>
          <Button onClick={openRegister}>{REGISTER_LABEL}</Button>
          <p className={styles.learnMore}>{LEARN_MORE_LABEL}</p>
        </div>
      ) : (
        <WebsitesTable rows={rows} />
      )}
      {registering ? (
        <RegisterWebsiteModal
          onClose={() => {
            setRegistering(false);
          }}
          onRegistered={() => {
            setRegistering(false);
          }}
        />
      ) : null}
    </Panel>
  );
}
