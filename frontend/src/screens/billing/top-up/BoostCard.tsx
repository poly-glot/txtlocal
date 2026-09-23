import { useId } from "react";

import type { Boost } from "@/api/generated/dashboard";
import { Icon } from "@/components/Icon/Icon";
import { Money } from "@/components/Money/Money";

import { estimateText } from "./rules";

import styles from "./BoostCard.module.css";

const TOP_UP_PREFIX = "Top-up";

interface Props {
  boost: Boost;
  country: string;
  onBuy: () => void;
  pending: boolean;
}

export function BoostCard({ boost, country, onBuy, pending }: Props) {
  const amountId = useId();

  return (
    <li className={styles.tile}>
      <div className={styles.head}>
        <span className={styles.amount} id={amountId}>
          {TOP_UP_PREFIX} <Money micro={boost.amountMicro} places={0} />
        </span>
        <button
          aria-labelledby={amountId}
          className={styles.add}
          disabled={pending}
          onClick={onBuy}
          type="button"
        >
          <Icon name="plus" />
        </button>
      </div>
      <p className={styles.estimate}>{estimateText(boost.estimate, country)}</p>
    </li>
  );
}
