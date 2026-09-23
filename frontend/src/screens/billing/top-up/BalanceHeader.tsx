import { useApiQuery } from "@/api/queries";
import { Badge } from "@/components/Badge/Badge";
import { Money } from "@/components/Money/Money";

import { autoRechargeText } from "./rules";

import styles from "./BalanceHeader.module.css";

const BALANCE_PREFIX = "Current credit balance:";
const CREDIT_NOTE = "Use your credit for any txtlocal product, including dedicated numbers.";
const CURRENCY_CODE = "GBP";
const CURRENCY_NOTE = "Prices are shown in British Pounds.";

export function BalanceHeader() {
  const summary = useApiQuery("get", "/api/app/billing/summary");

  if (summary.data === undefined) {
    return null;
  }
  if (summary.data.status === "ERROR") {
    return (
      <p className={styles.error} role="alert">
        {summary.data.message}
      </p>
    );
  }

  const { autoRecharge, balanceMicro } = summary.data.data;

  return (
    <header className={styles.header}>
      <div className={styles.headline}>
        <h2 className={styles.balance}>
          {BALANCE_PREFIX} <Money micro={balanceMicro} /> {CURRENCY_CODE}
        </h2>
        <Badge tone={autoRecharge ? "success" : "neutral"}>{autoRechargeText(autoRecharge)}</Badge>
      </div>
      <p className={styles.note}>
        {CREDIT_NOTE} {CURRENCY_NOTE}
      </p>
    </header>
  );
}
