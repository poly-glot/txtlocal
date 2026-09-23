import type { GeneralSettings } from "@/api/generated/dashboard";
import { Select } from "@/components/Select/Select";

import { AutoRechargeToggle } from "./AutoRechargeToggle";
import { BALANCE_THRESHOLD_OPTIONS, RECHARGE_AMOUNT_OPTIONS, optionsWithSaved } from "./rules";

import styles from "./BalanceManagementFields.module.css";

const ALERT_THRESHOLD_LABEL = "Send me an Email/SMS when my account balance goes below:";
const RECHARGE_AMOUNT_LABEL = "Top up by";
const RECHARGE_THRESHOLD_LABEL = "When my balance goes below";

interface Props {
  draft: GeneralSettings;
  onChange: (patch: Partial<GeneralSettings>) => void;
  saved: GeneralSettings;
}

export function BalanceManagementFields({ draft, onChange, saved }: Props) {
  return (
    <div className={styles.fields}>
      <AutoRechargeToggle
        checked={draft.autoRecharge}
        onChange={(autoRecharge) => {
          onChange({ autoRecharge });
        }}
      />
      {draft.autoRecharge ? (
        <div className={styles.amounts}>
          <Select
            id="general-recharge-amount"
            label={RECHARGE_AMOUNT_LABEL}
            onChange={(event) => {
              onChange({ rechargeAmountMicro: Number(event.target.value) });
            }}
            options={optionsWithSaved(RECHARGE_AMOUNT_OPTIONS, saved.rechargeAmountMicro)}
            value={String(draft.rechargeAmountMicro)}
          />
          <Select
            id="general-recharge-threshold"
            label={RECHARGE_THRESHOLD_LABEL}
            onChange={(event) => {
              onChange({ lowBalanceThresholdMicro: Number(event.target.value) });
            }}
            options={optionsWithSaved(BALANCE_THRESHOLD_OPTIONS, saved.lowBalanceThresholdMicro)}
            value={String(draft.lowBalanceThresholdMicro)}
          />
        </div>
      ) : null}
      <Select
        id="general-alert-threshold"
        label={ALERT_THRESHOLD_LABEL}
        onChange={(event) => {
          onChange({ alertThresholdMicro: Number(event.target.value) });
        }}
        options={optionsWithSaved(BALANCE_THRESHOLD_OPTIONS, saved.alertThresholdMicro)}
        value={String(draft.alertThresholdMicro)}
      />
    </div>
  );
}
