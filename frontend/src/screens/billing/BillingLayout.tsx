import { Outlet, useLocation, useNavigate } from "react-router";

import { Tabs } from "@/components/Tabs/Tabs";
import { BILLING_PATH } from "@/lib/paths";

import { BILLING_TABS } from "./billingTabs";

import styles from "./BillingLayout.module.css";

const LABELS = BILLING_TABS.map((tab) => tab.label);

export function BillingLayout() {
  const { pathname } = useLocation();
  const navigate = useNavigate();
  const current =
    BILLING_TABS.find((entry) => pathname === `${BILLING_PATH}/${entry.slug}`) ?? BILLING_TABS[0];

  return (
    <section className={styles.billing}>
      <Tabs
        onSelect={(label) => {
          const chosen = BILLING_TABS.find((entry) => entry.label === label) ?? BILLING_TABS[0];
          void navigate(`${BILLING_PATH}/${chosen.slug}`);
        }}
        selected={current.label}
        tabs={LABELS}
      />
      <Outlet />
    </section>
  );
}
