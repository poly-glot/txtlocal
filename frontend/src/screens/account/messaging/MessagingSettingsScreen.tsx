import { useState } from "react";

import { ComingSoon } from "@/components/ComingSoon/ComingSoon";
import { Tabs } from "@/components/Tabs/Tabs";

import { MessagingGeneralTab } from "./MessagingGeneralTab";

const CHANNEL_TABS = ["SMS & MMS"] as const;
const SUB_TABS = ["Inbound Rules", "Delivery Report Rules", "General", "Email SMS"] as const;

type SubTab = (typeof SUB_TABS)[number];

export function MessagingSettingsScreen() {
  const [tab, setTab] = useState<SubTab>("General");

  return (
    <section>
      <Tabs onSelect={() => undefined} selected="SMS & MMS" tabs={CHANNEL_TABS} />
      <Tabs onSelect={setTab} selected={tab} tabs={SUB_TABS} />
      {tab === "General" ? <MessagingGeneralTab /> : <ComingSoon name={tab} />}
    </section>
  );
}
