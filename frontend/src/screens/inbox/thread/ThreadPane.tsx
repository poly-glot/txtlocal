import { Panel } from "@/components/Panel/Panel";
import { PhoneNumber } from "@/components/PhoneNumber/PhoneNumber";
import type { Result } from "@/types";

import type { Selection } from "../rules";
import { ReplyComposer } from "./ReplyComposer";
import { ThreadView } from "./ThreadView";
import { SHARED_SENDER_VALUE } from "./rules";

import styles from "./ThreadPane.module.css";

const EMPTY_MSG = "Select a conversation to start sending";
const REGION_LABEL = "Conversation";

interface Props {
  notify: (result: Result<unknown>) => void;
  onSent: (peer: string) => void;
  selection: Selection | undefined;
  timezone: string | undefined;
}

interface NewThreadProps {
  notify: (result: Result<unknown>) => void;
  onSent: () => void;
  peer: string;
}

export function ThreadPane({ notify, onSent, selection, timezone }: Props) {
  if (selection === undefined) {
    return (
      <Panel>
        <section aria-label={REGION_LABEL} className={styles.pane}>
          <EmptyState />
        </section>
      </Panel>
    );
  }

  return (
    <Panel>
      <section aria-label={REGION_LABEL} className={styles.pane}>
        {selection.kind === "new" ? (
          <NewThread
            key={selection.peer}
            notify={notify}
            onSent={() => {
              onSent(selection.peer);
            }}
            peer={selection.peer}
          />
        ) : (
          <ThreadView
            key={selection.peer}
            notify={notify}
            peer={selection.peer}
            timezone={timezone}
          />
        )}
      </section>
    </Panel>
  );
}

function EmptyState() {
  return (
    <div className={styles.empty}>
      <svg aria-hidden="true" className={styles.illustration} viewBox="0 0 64 64">
        <path
          d="M8 12h48a4 4 0 0 1 4 4v24a4 4 0 0 1-4 4H24l-12 10V44H8a4 4 0 0 1-4-4V16a4 4 0 0 1 4-4Z"
          fill="none"
          stroke="currentColor"
          strokeLinejoin="round"
          strokeWidth="3"
        />
      </svg>
      <p className={styles.emptyText}>{EMPTY_MSG}</p>
    </div>
  );
}

function NewThread({ notify, onSent, peer }: NewThreadProps) {
  return (
    <>
      <header className={styles.header}>
        <PhoneNumber e164={peer} />
      </header>
      <ReplyComposer
        defaultSenderId={SHARED_SENDER_VALUE}
        notify={notify}
        onSent={onSent}
        peer={peer}
      />
    </>
  );
}
