import { useState } from "react";

import { Icon } from "@/components/Icon/Icon";
import { Input } from "@/components/Input/Input";
import { minuteValue } from "@/lib/format";

import { earliestSendAt, latestSendAt } from "../../rules";

import styles from "./SendNowButton.module.css";

const LATER_LABEL = "Schedule for later";
const SEND_AT_ID = "campaign-send-at";
const SEND_AT_LABEL = "Send at";
const SEND_NOW_LABEL = "SEND NOW";

interface Props {
  disabled: boolean;
  onChoose: (sendAt: string) => void;
}

export function SendNowButton({ disabled, onChoose }: Props) {
  const [picking, setPicking] = useState(false);
  const now = new Date();
  const earliest = minuteValue(earliestSendAt(now));

  return (
    <div className={styles.send}>
      {picking ? (
        <Input
          defaultValue={earliest}
          id={SEND_AT_ID}
          label={SEND_AT_LABEL}
          max={minuteValue(latestSendAt(now))}
          min={earliest}
          onChange={(event) => {
            if (event.target.value !== "") {
              onChoose(event.target.value);
            }
          }}
          type="datetime-local"
        />
      ) : null}
      <div className={styles.split}>
        <button
          className={styles.main}
          data-variant="primary"
          disabled={disabled}
          onClick={() => {
            onChoose("");
          }}
          type="button"
        >
          {SEND_NOW_LABEL}
        </button>
        <button
          aria-expanded={picking}
          aria-label={LATER_LABEL}
          className={styles.later}
          data-variant="primary"
          disabled={disabled}
          onClick={() => {
            setPicking(!picking);
          }}
          type="button"
        >
          <Icon name="chevron" />
        </button>
      </div>
    </div>
  );
}
