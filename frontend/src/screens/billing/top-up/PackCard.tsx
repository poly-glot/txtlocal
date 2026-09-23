import type { PowerPack } from "@/api/generated/dashboard";
import { Badge } from "@/components/Badge/Badge";
import { Button } from "@/components/Button/Button";
import { Money } from "@/components/Money/Money";

import { PER_SMS, estimateText, savingsText } from "./rules";

import styles from "./PackCard.module.css";

const CREDIT_SUFFIX = "of credit";
const TOP_UP_LABEL = "Top-up";

const topUpName = (name: string) => `Top-up ${name}`;

interface Props {
  country: string;
  onBuy: () => void;
  pack: PowerPack;
  pending: boolean;
}

export function PackCard({ country, onBuy, pack, pending }: Props) {
  return (
    <li className={styles.tile}>
      <div className={styles.head}>
        <div className={styles.titles}>
          <h4 className={styles.name}>{pack.name}</h4>
          <p className={styles.rate}>
            <Money micro={pack.rateMicro} places={4} /> {PER_SMS}
          </p>
        </div>
        <Badge tone="accent">{savingsText(pack.savingsPct)}</Badge>
      </div>
      <p className={styles.price}>
        <Money micro={pack.amountMicro} places={0} />
        <span className={styles.credit}>
          <Money micro={pack.creditedMicro} /> {CREDIT_SUFFIX}
        </span>
      </p>
      <Button aria-label={topUpName(pack.name)} disabled={pending} onClick={onBuy} variant="tonal">
        {TOP_UP_LABEL}
      </Button>
      <p className={styles.estimate}>{estimateText(pack.estimate, country)}</p>
    </li>
  );
}
