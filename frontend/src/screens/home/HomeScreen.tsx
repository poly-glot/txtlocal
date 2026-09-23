import { useState } from "react";

import { useApiQuery } from "@/api/queries";
import { PhonePreview } from "@/components/PhonePreview/PhonePreview";
import { StatusPanel } from "@/components/StatusPanel/StatusPanel";
import { Tabs } from "@/components/Tabs/Tabs";

import { GetStarted } from "./GetStarted";
import { SetupChecklist } from "./SetupChecklist";
import { TestSend } from "./TestSend";
import { TrialStats } from "./TrialStats";
import { WelcomeCard } from "./WelcomeCard";

import styles from "./HomeScreen.module.css";

const CAPTION = "Preview on a handset";
const HEADER = "SENDER ID";
const HOME_TABS = ["SEND A TEST MESSAGE", "GET STARTED WITH TXTLOCAL"] as const;

type HomeTab = (typeof HOME_TABS)[number];

export function HomeScreen() {
  const home = useApiQuery("get", "/api/app/home");
  const [body, setBody] = useState("");
  const [tab, setTab] = useState<HomeTab>(HOME_TABS[0]);

  if (home.data === undefined) {
    return <StatusPanel />;
  }
  if (home.data.status === "ERROR") {
    return <StatusPanel error={home.data.message} />;
  }

  const dashboard = home.data.data;

  return (
    <div className={styles.page}>
      <WelcomeCard
        firstName={dashboard.firstName}
        lastName={dashboard.lastName}
        trialDaysLeft={dashboard.trialDaysLeft}
      />
      <div className={styles.columns}>
        <section className={styles.composer}>
          <Tabs onSelect={setTab} selected={tab} tabs={HOME_TABS} />
          <div className={styles.panel} role="tabpanel">
            {tab === "SEND A TEST MESSAGE" ? (
              <div className={styles.split}>
                <TestSend
                  balanceMicro={dashboard.balanceMicro}
                  body={body}
                  onBodyChange={setBody}
                />
                <PhonePreview body={body} caption={CAPTION} title={HEADER} />
              </div>
            ) : (
              <GetStarted />
            )}
          </div>
        </section>
        <aside className={styles.rail}>
          <SetupChecklist
            emailVerified={dashboard.emailVerified}
            numberVerified={dashboard.numberVerified}
          />
          <TrialStats trialDaysLeft={dashboard.trialDaysLeft} />
        </aside>
      </div>
    </div>
  );
}
