import type { UnicodeMode } from "@/api/generated/dashboard";

import styles from "./UnicodeChoice.module.css";

const AUTODETECT_INFO =
  "Autodetect: Will allow normal GSM characters and unicode characters (e.g. English, French and Chinese Characters)";
const AUTODETECT_LABEL = "Autodetect";
const FORCE_GSM_INFO =
  "Force non-unicode: Will only allow GSM characters http://en.wikipedia.org/wiki/GSM_03.38";
const FORCE_GSM_LABEL = "Force non unicode (GSM Characters only)";
const LEGEND = "Select Unicode SMS:";

interface Props {
  onChange: (mode: UnicodeMode) => void;
  value: UnicodeMode;
}

export function UnicodeChoice({ onChange, value }: Props) {
  return (
    <fieldset className={styles.fieldset}>
      <legend className={styles.legend}>{LEGEND}</legend>
      <label className={styles.option}>
        <input
          checked={value === "AUTODETECT"}
          name="unicode-mode"
          onChange={() => {
            onChange("AUTODETECT");
          }}
          type="radio"
        />
        {AUTODETECT_LABEL}
      </label>
      <label className={styles.option}>
        <input
          checked={value === "GSM_ONLY"}
          name="unicode-mode"
          onChange={() => {
            onChange("GSM_ONLY");
          }}
          type="radio"
        />
        {FORCE_GSM_LABEL}
      </label>
      <div className={styles.info}>
        <p className={styles.line}>{AUTODETECT_INFO}</p>
        <p className={styles.line}>{FORCE_GSM_INFO}</p>
      </div>
    </fieldset>
  );
}
