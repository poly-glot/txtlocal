import { useState } from "react";

import { useApiMutation } from "@/api/queries";
import { Panel } from "@/components/Panel/Panel";
import { SearchForm } from "@/components/SearchForm/SearchForm";
import type { Result } from "@/types";

import { ConversationList } from "./ConversationList";
import { ConversationsToolbar } from "./ConversationsToolbar";
import { NewNumberPrompt } from "./NewNumberPrompt";
import type { StatusFilter } from "./rules";

import styles from "./ConversationListPane.module.css";

const SEARCH_LABEL = "Search";
const SEARCH_PLACEHOLDER = "Type a name, mobile number or phrase to find or start a conversation";
const TITLE = "Inbox";

interface Props {
  notify: (result: Result<unknown>) => void;
  onSelect: (peer: string) => void;
  onStartNew: (peer: string) => void;
  selectedPeer: string | undefined;
  timezone: string | undefined;
}

export function ConversationListPane({
  notify,
  onSelect,
  onStartNew,
  selectedPeer,
  timezone,
}: Props) {
  const [status, setStatus] = useState<StatusFilter>("OPEN");
  const [q, setQ] = useState("");
  const [composeOpen, setComposeOpen] = useState(false);
  const markAllRead = useApiMutation("post", "/api/app/conversations/read-all");

  return (
    <Panel title={TITLE}>
      <div className={styles.body}>
        <ConversationsToolbar
          onMarkAllRead={() => {
            markAllRead.mutate(undefined, { onSuccess: notify });
          }}
          onStatusChange={setStatus}
          onToggleCompose={() => {
            setComposeOpen(!composeOpen);
          }}
          status={status}
        />
        {composeOpen ? (
          <NewNumberPrompt
            onCancel={() => {
              setComposeOpen(false);
            }}
            onStart={(peer) => {
              setComposeOpen(false);
              onStartNew(peer);
            }}
          />
        ) : null}
        <SearchForm
          id="inbox-search"
          label={SEARCH_LABEL}
          onSearch={setQ}
          placeholder={SEARCH_PLACEHOLDER}
        />
        <ConversationList
          notify={notify}
          onSelect={onSelect}
          onStartNew={onStartNew}
          q={q}
          selectedPeer={selectedPeer}
          status={status}
          timezone={timezone}
        />
      </div>
    </Panel>
  );
}
