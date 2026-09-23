import { useApiMutation, useApiQuery } from "@/api/queries";
import { StatusMessage } from "@/components/StatusMessage/StatusMessage";
import type { Result } from "@/types";

import { POLL_MS } from "../rules";
import { ConversationRow } from "./ConversationRow";
import type { StatusFilter } from "./rules";
import { looksLikeNumber, statusQueryValue } from "./rules";

import styles from "./ConversationList.module.css";

const EMPTY_MSG = "No conversations found.";

const startLabel = (peer: string) => `Start a conversation with ${peer}`;

interface Props {
  notify: (result: Result<unknown>) => void;
  onSelect: (peer: string) => void;
  onStartNew: (peer: string) => void;
  q: string;
  selectedPeer: string | undefined;
  status: StatusFilter;
  timezone: string | undefined;
}

export function ConversationList({
  notify,
  onSelect,
  onStartNew,
  q,
  selectedPeer,
  status,
  timezone,
}: Props) {
  const search = q.trim();
  const conversations = useApiQuery(
    "get",
    "/api/app/conversations",
    {
      params: {
        query: { cursor: null, q: search === "" ? null : search, status: statusQueryValue(status) },
      },
    },
    { refetchInterval: POLL_MS },
  );
  const markRead = useApiMutation("post", "/api/app/conversations/{peer}/read");

  if (conversations.data === undefined) {
    return <StatusMessage />;
  }
  if (conversations.data.status === "ERROR") {
    return <StatusMessage error={conversations.data.message} />;
  }

  const { items } = conversations.data.data;

  if (items.length === 0 && looksLikeNumber(search)) {
    return (
      <button
        className={styles.startNew}
        onClick={() => {
          onStartNew(search);
        }}
        type="button"
      >
        {startLabel(search)}
      </button>
    );
  }
  if (items.length === 0) {
    return <p className={styles.empty}>{EMPTY_MSG}</p>;
  }

  return (
    <ul className={styles.rows}>
      {items.map((conversation) => (
        <ConversationRow
          active={conversation.peer === selectedPeer}
          conversation={conversation}
          key={conversation.peer}
          onSelect={() => {
            markRead.mutate(
              { params: { path: { peer: conversation.peer } } },
              { onSuccess: notify },
            );
            onSelect(conversation.peer);
          }}
          timezone={timezone}
        />
      ))}
    </ul>
  );
}
