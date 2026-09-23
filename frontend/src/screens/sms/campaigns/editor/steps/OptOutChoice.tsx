import type { OptOutMode } from "./rules";

import styles from "./OptOutChoice.module.css";

const FOOTER_ID = "campaign-footer";
const FOOTER_LABEL = "Footer";
const LEGEND = "Opt-out";
const MODES = [
  { label: "Reply STOP", value: "REPLY_STOP" },
  { label: "Unsubscribe Link", value: "UNSUBSCRIBE_LINK" },
] as const;

interface Props {
  footer: string;
  mode: OptOutMode;
  onFooterChange: (footer: string) => void;
  onModeChange: (mode: OptOutMode) => void;
}

export function OptOutChoice({ footer, mode, onFooterChange, onModeChange }: Props) {
  return (
    <fieldset className={styles.fieldset}>
      <legend className={styles.legend}>{LEGEND}</legend>
      {MODES.map((choice) => (
        <label className={styles.option} key={choice.value}>
          <input
            checked={mode === choice.value}
            name="campaign-opt-out"
            onChange={() => {
              onModeChange(choice.value);
            }}
            type="radio"
          />
          {choice.label}
        </label>
      ))}
      <label className={styles.label} htmlFor={FOOTER_ID}>
        {FOOTER_LABEL}
      </label>
      <input
        className={styles.input}
        id={FOOTER_ID}
        onChange={(event) => {
          onFooterChange(event.target.value);
        }}
        value={footer}
      />
    </fieldset>
  );
}
