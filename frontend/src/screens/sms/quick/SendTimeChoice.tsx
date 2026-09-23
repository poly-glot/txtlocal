import { minuteValue } from "@/lib/format";

import { NOW_LABEL, earliestSendAt, latestSendAt } from "../rules";

import styles from "./SendTimeChoice.module.css";

const AT_LABEL = "Send at";
const LATER_LABEL = "Later";
const SEND_TIME_LABEL = "Send Time";

interface Props {
  onChange: (sendAt: string) => void;
  sendAt: string;
}

export function SendTimeChoice({ onChange, sendAt }: Props) {
  const now = new Date();
  const earliest = minuteValue(earliestSendAt(now));

  return (
    <fieldset className={styles.fieldset}>
      <legend className={styles.legend}>{SEND_TIME_LABEL}</legend>
      <label className={styles.option}>
        <input
          checked={sendAt === ""}
          name="send-time"
          onChange={() => {
            onChange("");
          }}
          type="radio"
        />
        {NOW_LABEL}
      </label>
      <label className={styles.option}>
        <input
          checked={sendAt !== ""}
          name="send-time"
          onChange={() => {
            onChange(earliest);
          }}
          type="radio"
        />
        {LATER_LABEL}
      </label>
      {sendAt === "" ? null : (
        <div className={styles.picker}>
          <label className={styles.label} htmlFor="quick-send-at">
            {AT_LABEL}
          </label>
          <input
            className={styles.input}
            id="quick-send-at"
            max={minuteValue(latestSendAt(now))}
            min={earliest}
            onChange={(event) => {
              onChange(event.target.value);
            }}
            type="datetime-local"
            value={sendAt}
          />
        </div>
      )}
    </fieldset>
  );
}
