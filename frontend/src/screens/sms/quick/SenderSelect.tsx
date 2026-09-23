import { Link } from "react-router";

import type { SendersView } from "@/api/generated/dashboard";

import { SMART_SENDERS_LABEL } from "../rules";

import styles from "./SenderSelect.module.css";

const FROM_LABEL = "From";
const HELPER =
  "The best sender has been auto-selected from Smart Senders. Reset the Smart Sender for each country. Or select an approved number or sender above.";
const HELPER_ID = "quick-from-helper";
const GROUPS = [
  { action: "", kind: "SHARED", label: SMART_SENDERS_LABEL, to: "" },
  { action: "Purchase", kind: "DEDICATED", label: "Dedicated Numbers", to: "/senders/buy" },
  { action: "Add", kind: "ALPHA", label: "Alpha Tags", to: "/senders" },
  { action: "Add", kind: "OWN", label: "Own Numbers", to: "/senders" },
] as const;

interface Props {
  onChange: (senderId: string) => void;
  senders: SendersView["senders"];
  value: string;
}

export function SenderSelect({ onChange, senders, value }: Props) {
  const groups = GROUPS.map((group) => ({ ...group, options: senders[group.kind] ?? [] }));

  return (
    <div className={styles.field}>
      <label className={styles.label} htmlFor="quick-from">
        {FROM_LABEL}
      </label>
      <select
        aria-describedby={HELPER_ID}
        className={styles.select}
        id="quick-from"
        onChange={(event) => {
          onChange(event.target.value);
        }}
        value={value}
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
      <p className={styles.helper} id={HELPER_ID}>
        {HELPER}
      </p>
      <p className={styles.links}>
        {groups
          .filter((group) => group.action !== "" && group.options.length === 0)
          .map((group) => (
            <Link className={styles.link} key={group.kind} to={group.to}>
              {`${group.action} ${group.label}`}
            </Link>
          ))}
      </p>
    </div>
  );
}
