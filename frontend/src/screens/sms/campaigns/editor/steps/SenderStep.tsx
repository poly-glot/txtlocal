import { Link } from "react-router";

import type { SendersView } from "@/api/generated/dashboard";

import type { ScreenProduct } from "../../../rules";
import { SMART_SENDERS_LABEL } from "../../../rules";
import { StepSection } from "./StepSection";
import { senderTitle } from "./rules";

import styles from "./SenderStep.module.css";

const FROM_ID = "campaign-from";
const FROM_LABEL = "From";
const GROUPS = [
  { kind: "SHARED", label: SMART_SENDERS_LABEL },
  { kind: "DEDICATED", label: "Dedicated Numbers" },
  { kind: "ALPHA", label: "Alpha Tags" },
  { kind: "OWN", label: "Own Numbers" },
] as const;
const REPLIES_LABEL = "Where do contacts' replies go?";
const REPLIES_PATH = "/account/messaging";
const STEP = 2;

interface Props {
  onChange: (senderId: string) => void;
  product: ScreenProduct;
  senderId: string;
  senders: SendersView;
}

export function SenderStep({ onChange, product, senderId, senders }: Props) {
  const groups = GROUPS.map((group) => ({ ...group, options: senders.senders[group.kind] ?? [] }));

  return (
    <StepSection complete step={STEP} subtitle={senderTitle(product)} title={FROM_LABEL}>
      <div className={styles.field}>
        <label className={styles.label} htmlFor={FROM_ID}>
          {FROM_LABEL}
        </label>
        <select
          className={styles.select}
          id={FROM_ID}
          onChange={(event) => {
            onChange(event.target.value);
          }}
          value={senderId}
        >
          <option value="">{SMART_SENDERS_LABEL}</option>
          {groups
            .filter((group) => group.options.length > 0)
            .map((group) => (
              <optgroup key={group.kind} label={group.label}>
                {group.options.map((sender) => (
                  <option key={sender.senderId} value={sender.senderId}>
                    {sender.display}
                  </option>
                ))}
              </optgroup>
            ))}
        </select>
      </div>
      {product === "MMS" ? (
        <Link className={styles.link} to={REPLIES_PATH}>
          {REPLIES_LABEL}
        </Link>
      ) : null}
    </StepSection>
  );
}
