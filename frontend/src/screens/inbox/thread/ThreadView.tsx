import { useApiMutation, useApiQuery } from "@/api/queries";
import { Button } from "@/components/Button/Button";
import { PhoneNumber } from "@/components/PhoneNumber/PhoneNumber";
import { StatusMessage } from "@/components/StatusMessage/StatusMessage";
import type { Result } from "@/types";

import { POLL_MS } from "../rules";
import { MessageList } from "./MessageList";
import { ReplyComposer } from "./ReplyComposer";
import { chronological, defaultSenderId, toggleStatusLabel } from "./rules";

import styles from "./ThreadView.module.css";

interface Props {
  notify: (result: Result<unknown>) => void;
  peer: string;
  timezone: string | undefined;
}

export function ThreadView({ notify, peer, timezone }: Props) {
  const thread = useApiQuery(
    "get",
    "/api/app/conversations/{peer}",
    { params: { path: { peer } } },
    { refetchInterval: POLL_MS },
  );
  const close = useApiMutation("post", "/api/app/conversations/{peer}/close");
  const reopen = useApiMutation("post", "/api/app/conversations/{peer}/reopen");

  if (thread.data === undefined) {
    return <StatusMessage />;
  }
  if (thread.data.status === "ERROR") {
    return <StatusMessage error={thread.data.message} />;
  }

  const { conversation, messages, replyHint } = thread.data.data;

  const toggleStatus = () => {
    const mutation = conversation.status === "OPEN" ? close : reopen;
    mutation.mutate({ params: { path: { peer } } }, { onSuccess: notify });
  };

  return (
    <>
      <header className={styles.header}>
        <div className={styles.contact}>
          <h2 className={styles.name}>{conversation.name}</h2>
          <span className={styles.number}>
            <PhoneNumber e164={conversation.peer} />
          </span>
        </div>
        <Button onClick={toggleStatus} variant="secondary">
          {toggleStatusLabel(conversation.status)}
        </Button>
      </header>
      <MessageList messages={chronological(messages.items)} timezone={timezone} />
      <ReplyComposer
        defaultSenderId={defaultSenderId(conversation.lastSenderId)}
        hint={replyHint}
        notify={notify}
        peer={peer}
      />
    </>
  );
}
