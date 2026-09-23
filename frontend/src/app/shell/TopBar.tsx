import { Link, useLocation } from "react-router";

import { useApiQuery } from "@/api/queries";
import { Icon } from "@/components/Icon/Icon";
import { Money } from "@/components/Money/Money";
import { API_CREDENTIALS_PATH, API_DOCS_PATH, BILLING_TOP_UP_PATH } from "@/lib/paths";

import { AvatarMenu } from "./AvatarMenu";
import { titleOf } from "./rules";

import styles from "./TopBar.module.css";

const LANGUAGE = "English";
const TOP_UP_NOW = "Top up now";

const trialBannerText = (days: number) =>
  `Only ${String(days)} days to use your free trial credit. Top up for full access.`;

interface BannerProps {
  days: number;
}

export function TopBar() {
  const { pathname } = useLocation();
  const me = useApiQuery("get", "/api/app/me");
  const account = me.data?.status === "OK" ? me.data.data : undefined;

  return (
    <header className={styles.bar}>
      <h1 className={styles.title}>{titleOf(pathname)}</h1>
      {account !== undefined && !account.hasToppedUp ? (
        <TrialBanner days={account.trialDaysLeft} />
      ) : null}
      <div className={styles.funds}>
        {account === undefined ? null : (
          <span className={styles.balance}>
            Balance: <Money micro={account.balanceMicro} />
          </span>
        )}
        <Link aria-label="Top up" className={styles.topUp} to={BILLING_TOP_UP_PATH}>
          <Icon name="plus" />
        </Link>
      </div>
      <div className={styles.actions}>
        <Link aria-label="Help" className={styles.action} to={API_DOCS_PATH}>
          <Icon name="help" size={20} />
        </Link>
        <button aria-label="Notifications" className={styles.action} disabled type="button">
          <Icon name="bell" size={20} />
        </button>
        <Link aria-label="API Credentials" className={styles.action} to={API_CREDENTIALS_PATH}>
          <Icon name="key" size={20} />
        </Link>
        {account === undefined ? null : <AvatarMenu me={account} />}
        <span className={styles.language}>{LANGUAGE}</span>
      </div>
    </header>
  );
}

function TrialBanner({ days }: BannerProps) {
  return (
    <p className={styles.banner}>
      <Icon name="alert" />
      <span className={styles.bannerText}>{trialBannerText(days)}</span>
      <Link className={styles.bannerLink} to={BILLING_TOP_UP_PATH}>
        {TOP_UP_NOW}
      </Link>
    </p>
  );
}
