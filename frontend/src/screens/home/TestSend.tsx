import { useState } from "react";
import type { SubmitEvent } from "react";

import { useApiMutation } from "@/api/queries";
import { Button } from "@/components/Button/Button";
import { Icon } from "@/components/Icon/Icon";
import { Input } from "@/components/Input/Input";
import { Toast } from "@/components/Toast/Toast";
import type { Notice } from "@/types";

import { MessageField } from "./MessageField";
import { recipientsOf, testSendNotice, testSendRequest } from "./rules";

import styles from "./TestSend.module.css";

const RECIPIENT_HELPER =
  "Start typing a number. You can enter multiple numbers separated by a comma.";
const RECIPIENT_PLACEHOLDER = "Enter phone number";
const SENDER_HELPER =
  "This is your temporary Sender ID for testing. You can set up your own whenever you're ready.";
const SENDER_VALUE = "txtlocal Sender ID";
const SUBMIT_LABEL = "SEND TEST MESSAGE";

interface Props {
  balanceMicro: number;
  body: string;
  onBodyChange: (body: string) => void;
}

export function TestSend({ balanceMicro, body, onBodyChange }: Props) {
  const [recipient, setRecipient] = useState("");
  const [notice, setNotice] = useState<Notice>();
  const send = useApiMutation("post", "/api/app/messages/send");
  const recipients = recipientsOf(recipient);
  const ready = recipients.length > 0 && body.trim() !== "";

  const submit = (event: SubmitEvent<HTMLFormElement>) => {
    event.preventDefault();
    send.mutate(
      { body: testSendRequest(body, recipients) },
      {
        onSuccess: (result) => {
          setNotice(testSendNotice(result));
          if (result.status === "OK") {
            onBodyChange("");
            setRecipient("");
          }
        },
      },
    );
  };

  return (
    <form className={styles.form} onSubmit={submit}>
      <Input
        helper={RECIPIENT_HELPER}
        id="test-recipient"
        label="Recipient"
        onChange={(event) => {
          setRecipient(event.target.value);
        }}
        placeholder={RECIPIENT_PLACEHOLDER}
        value={recipient}
      />
      <Input
        helper={SENDER_HELPER}
        id="test-sender"
        label="Sender ID"
        readOnly
        value={SENDER_VALUE}
      />
      <MessageField balanceMicro={balanceMicro} body={body} onChange={onBodyChange} />
      <Toast
        notice={notice}
        onDismiss={() => {
          setNotice(undefined);
        }}
      />
      <Button disabled={!ready || send.isPending} type="submit">
        <Icon name="send" />
        {SUBMIT_LABEL}
      </Button>
    </form>
  );
}
