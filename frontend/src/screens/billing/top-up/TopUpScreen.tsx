import { useState } from "react";
import { useSearchParams } from "react-router";

import { useApiQuery } from "@/api/queries";
import { Money } from "@/components/Money/Money";
import { Panel } from "@/components/Panel/Panel";
import { StatusPanel } from "@/components/StatusPanel/StatusPanel";
import { Toast } from "@/components/Toast/Toast";
import type { Notice } from "@/types";

import { BalanceHeader } from "./BalanceHeader";
import { BoostCard } from "./BoostCard";
import { PackCard } from "./PackCard";
import { TopUpOutcome } from "./TopUpOutcome";
import { PER_SMS } from "./rules";
import { useTopUpCheckout } from "./useTopUpCheckout";

import styles from "./TopUpScreen.module.css";

const BOOSTS_TITLE = "Credit boost";
const PACKS_SUBTITLE = "Bigger top-ups. Bigger savings.";
const PACKS_TITLE = "Power packs";
const PRICING_COUNTRY = "GB";

export function TopUpScreen() {
  const [params] = useSearchParams();
  const topUpId = params.get("topup") ?? undefined;
  const packages = useApiQuery("get", "/api/app/billing/packages", {
    params: { query: { country: PRICING_COUNTRY } },
  });
  const [notice, setNotice] = useState<Notice>();
  const { buy, pendingCode } = useTopUpCheckout((message) => {
    setNotice({ message, tone: "error" });
  });

  if (packages.data === undefined) {
    return <StatusPanel />;
  }
  if (packages.data.status === "ERROR") {
    return <StatusPanel error={packages.data.message} />;
  }

  const { boosts, packs, rateMicro } = packages.data.data;

  return (
    <Panel>
      {topUpId === undefined ? null : <TopUpOutcome topUpId={topUpId} />}
      <Toast
        notice={notice}
        onDismiss={() => {
          setNotice(undefined);
        }}
      />
      <BalanceHeader />
      <section className={styles.boosts}>
        <div className={styles.intro}>
          <h3 className={styles.title}>{BOOSTS_TITLE}</h3>
          <p className={styles.subtitle}>
            <Money micro={rateMicro} places={4} /> {PER_SMS}
          </p>
        </div>
        <ul className={styles.boostGrid}>
          {boosts.map((boost) => (
            <BoostCard
              boost={boost}
              country={PRICING_COUNTRY}
              key={boost.code}
              onBuy={() => {
                buy({ code: boost.code, kind: "BOOST" });
              }}
              pending={pendingCode === boost.code}
            />
          ))}
        </ul>
      </section>
      <section className={styles.packs}>
        <div className={styles.intro}>
          <h3 className={styles.title}>{PACKS_TITLE}</h3>
          <p className={styles.subtitle}>{PACKS_SUBTITLE}</p>
        </div>
        <ul className={styles.packGrid}>
          {packs.map((pack) => (
            <PackCard
              country={PRICING_COUNTRY}
              key={pack.code}
              onBuy={() => {
                buy({ code: pack.code, kind: "PACK" });
              }}
              pack={pack}
              pending={pendingCode === pack.code}
            />
          ))}
        </ul>
      </section>
    </Panel>
  );
}
