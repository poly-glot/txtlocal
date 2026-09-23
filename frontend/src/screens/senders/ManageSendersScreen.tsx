import { useState } from "react";

import type { SendersView } from "@/api/generated/dashboard";
import { useApiQuery } from "@/api/queries";
import { Panel } from "@/components/Panel/Panel";
import { StatusPanel } from "@/components/StatusPanel/StatusPanel";
import { Tabs } from "@/components/Tabs/Tabs";

import { SmartSendersTab } from "./SmartSendersTab";
import { AlphaTagsTab } from "./alpha-tags/AlphaTagsTab";
import { MyNumbersTab } from "./my-numbers/MyNumbersTab";

import styles from "./ManageSendersScreen.module.css";

const TABS = ["Smart Senders", "My Numbers", "Alpha Tags"] as const;

type Tab = (typeof TABS)[number];

export function ManageSendersScreen() {
  const senders = useApiQuery("get", "/api/app/senders");
  const [tab, setTab] = useState<Tab>(TABS[0]);

  if (senders.data === undefined) {
    return <StatusPanel />;
  }
  if (senders.data.status === "ERROR") {
    return <StatusPanel error={senders.data.message} />;
  }

  return (
    <Panel>
      <div className={styles.body}>
        <Tabs onSelect={setTab} selected={tab} tabs={TABS} />
        <div role="tabpanel">{panelFor(tab, senders.data.data)}</div>
      </div>
    </Panel>
  );
}

function panelFor(tab: Tab, view: SendersView) {
  switch (tab) {
    case "Smart Senders":
      return <SmartSendersTab view={view} />;
    case "My Numbers":
      return <MyNumbersTab view={view} />;
    case "Alpha Tags":
      return <AlphaTagsTab view={view} />;
  }
}
