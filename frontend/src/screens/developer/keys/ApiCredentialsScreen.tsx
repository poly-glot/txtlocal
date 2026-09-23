import { useState } from "react";

import { Tabs } from "@/components/Tabs/Tabs";

import { ApiGeneralTab } from "./ApiGeneralTab";
import { SubaccountsTab } from "./SubaccountsTab";

const TABS = ["Subaccounts", "General"] as const;

type Tab = (typeof TABS)[number];

export function ApiCredentialsScreen() {
  const [tab, setTab] = useState<Tab>("Subaccounts");

  return (
    <section>
      <Tabs onSelect={setTab} selected={tab} tabs={TABS} />
      {tab === "Subaccounts" ? <SubaccountsTab /> : <ApiGeneralTab />}
    </section>
  );
}
