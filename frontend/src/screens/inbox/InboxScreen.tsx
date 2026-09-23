import { useState } from "react";

import { Toast } from "@/components/Toast/Toast";
import { refusalNotice } from "@/lib/notice";
import { useAccountTimezone } from "@/lib/useAccountTimezone";
import type { Notice, Result } from "@/types";

import { ConversationListPane } from "./conversations/ConversationListPane";
import type { Selection } from "./rules";
import { ThreadPane } from "./thread/ThreadPane";

import styles from "./InboxScreen.module.css";

export function InboxScreen() {
  const [selection, setSelection] = useState<Selection>();
  const [notice, setNotice] = useState<Notice>();
  const timezone = useAccountTimezone();

  const notify = (result: Result<unknown>) => {
    setNotice((current) => refusalNotice(result) ?? current);
  };

  return (
    <div className={styles.page}>
      <Toast
        notice={notice}
        onDismiss={() => {
          setNotice(undefined);
        }}
      />
      <div className={styles.panels}>
        <ConversationListPane
          notify={notify}
          onSelect={(peer) => {
            setSelection({ kind: "thread", peer });
          }}
          onStartNew={(peer) => {
            setSelection({ kind: "new", peer });
          }}
          selectedPeer={selection?.peer}
          timezone={timezone}
        />
        <ThreadPane
          notify={notify}
          onSent={(peer) => {
            setSelection({ kind: "thread", peer });
          }}
          selection={selection}
          timezone={timezone}
        />
      </div>
    </div>
  );
}
