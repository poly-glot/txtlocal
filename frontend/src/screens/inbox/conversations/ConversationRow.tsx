import type { ConversationView } from "@/api/generated/dashboard";
import { Badge } from "@/components/Badge/Badge";
import { PhoneNumber } from "@/components/PhoneNumber/PhoneNumber";

import { initialsOf, relativeTimeOf } from "./rules";

import styles from "./ConversationRow.module.css";

interface Props {
  active: boolean;
  conversation: ConversationView;
  onSelect: () => void;
  timezone: string | undefined;
}

export function ConversationRow({ active, conversation, onSelect, timezone }: Props) {
  const unread = conversation.unread > 0;
  const isNumber = conversation.name === conversation.peer;

  return (
    <li className={styles.row}>
      <button
        aria-current={active}
        className={styles.open}
        data-unread={unread}
        onClick={onSelect}
        type="button"
      >
        <span aria-hidden="true" className={styles.avatar}>
          {initialsOf(conversation.name)}
        </span>
        <span className={styles.body}>
          <span className={styles.top}>
            <span className={styles.name}>
              {isNumber ? <PhoneNumber e164={conversation.peer} /> : conversation.name}
            </span>
            <span className={styles.time}>
              {relativeTimeOf(conversation.lastAt, new Date(), timezone)}
            </span>
          </span>
          <span className={styles.preview}>{conversation.lastPreview}</span>
        </span>
        {unread ? <Badge tone="success">{conversation.unread}</Badge> : null}
      </button>
    </li>
  );
}
