import styles from "./AutoRechargeToggle.module.css";

const AUTO_RECHARGE_HELPER =
  "If you purchase a dedicated number, auto recharge will be automatically enabled at the end of each month. This can be stopped by cancelling the number.";
const AUTO_RECHARGE_ID = "billing-auto-recharge";
const AUTO_RECHARGE_LABEL = "Automatically top up my account";
const HELPER_ID = `${AUTO_RECHARGE_ID}-helper`;

interface Props {
  checked: boolean;
  onChange: (checked: boolean) => void;
}

export function AutoRechargeToggle({ checked, onChange }: Props) {
  return (
    <div className={styles.row}>
      <div className={styles.text}>
        <label className={styles.label} htmlFor={AUTO_RECHARGE_ID}>
          {AUTO_RECHARGE_LABEL}
        </label>
        <p className={styles.helper} id={HELPER_ID}>
          {AUTO_RECHARGE_HELPER}
        </p>
      </div>
      <input
        aria-describedby={HELPER_ID}
        checked={checked}
        className={styles.switch}
        id={AUTO_RECHARGE_ID}
        onChange={(event) => {
          onChange(event.target.checked);
        }}
        role="switch"
        type="checkbox"
      />
    </div>
  );
}
