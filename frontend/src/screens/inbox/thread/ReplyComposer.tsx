import { useState } from "react";

import { useApiMutation, useApiQuery } from "@/api/queries";
import { Button } from "@/components/Button/Button";
import { Icon } from "@/components/Icon/Icon";
import { Select } from "@/components/Select/Select";
import { StatusMessage } from "@/components/StatusMessage/StatusMessage";
import { segmentSummary, segmentsOf } from "@/rules/segments";
import type { Result } from "@/types";

import { senderIdOf, senderOptions } from "./rules";

import styles from "./ReplyComposer.module.css";

const BODY_LABEL = "Message";
const FROM_LABEL = "From";
const SEND_LABEL = "SEND";

interface Props {
  defaultSenderId: string;
  hint?: string;
  notify: (result: Result<unknown>) => void;
  onSent?: () => void;
  peer: string;
}

export function ReplyComposer({ defaultSenderId, hint, notify, onSent, peer }: Props) {
  const [senderId, setSenderId] = useState(defaultSenderId);
  const [body, setBody] = useState("");
  const senders = useApiQuery("get", "/api/app/senders");
  const reply = useApiMutation("post", "/api/app/conversations/{peer}/messages");

  if (senders.data === undefined) {
    return <StatusMessage />;
  }
  if (senders.data.status === "ERROR") {
    return <StatusMessage error={senders.data.message} />;
  }

  const send = () => {
    reply.mutate(
      { body: { body, senderId: senderIdOf(senderId) }, params: { path: { peer } } },
      {
        onSuccess: (result) => {
          notify(result);
          if (result.status === "OK") {
            setBody("");
            onSent?.();
          }
        },
      },
    );
  };

  return (
    <div className={styles.composer}>
      {hint === undefined ? null : <p className={styles.hint}>{hint}</p>}
      <Select
        id="reply-from"
        label={FROM_LABEL}
        onChange={(event) => {
          setSenderId(event.target.value);
        }}
        options={senderOptions(senders.data.data.senders)}
        value={senderId}
      />
      <label className={styles.label} htmlFor="reply-body">
        {BODY_LABEL}
      </label>
      <textarea
        className={styles.textarea}
        id="reply-body"
        onChange={(event) => {
          setBody(event.target.value);
        }}
        rows={4}
        value={body}
      />
      <div className={styles.footer}>
        <p className={styles.counter}>{segmentSummary(segmentsOf(body))}</p>
        <Button disabled={body.trim() === "" || reply.isPending} onClick={send}>
          <Icon name="send" />
          {SEND_LABEL}
        </Button>
      </div>
    </div>
  );
}
