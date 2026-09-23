import { useState } from "react";
import type { SubmitEvent } from "react";

import type { SenderView } from "@/api/generated/dashboard";
import { useApiMutation } from "@/api/queries";
import { Button } from "@/components/Button/Button";
import { Modal } from "@/components/Modal/Modal";
import { Toast } from "@/components/Toast/Toast";
import type { Notice, Result } from "@/types";

import { AddOwnNumberFields } from "./AddOwnNumberFields";
import type { OwnNumberDraft } from "./rules";
import { dialled, isVerificationCode } from "./rules";

import styles from "./AddOwnNumberModal.module.css";

const ADD_LABEL = "Add Number";
const CANCEL_LABEL = "Cancel";
const COPY =
  "Follow the steps below to add your own number. We'll send you a code to verify your number.";
const TITLE = "Add your own number";
const TITLE_ID = "add-own-number-title";

interface Props {
  initial: OwnNumberDraft;
  onClose: () => void;
}

export function AddOwnNumberModal({ initial, onClose }: Props) {
  const [draft, setDraft] = useState(initial);
  const [notice, setNotice] = useState<Notice>();
  const [senderId, setSenderId] = useState<string>();
  const add = useApiMutation("post", "/api/app/senders/own");
  const verify = useApiMutation("post", "/api/app/senders/own/{senderId}/verify");

  const settle = (result: Result<SenderView>, accept: (sender: SenderView) => void) => {
    if (result.status === "ERROR") {
      setNotice({ message: result.message, tone: "error" });
      return;
    }
    accept(result.data);
  };

  const sendCode = () => {
    const nickname = draft.nickname === "" ? null : draft.nickname;
    add.mutate(
      { body: { nickname, number: dialled(draft.country, draft.number) } },
      {
        onSuccess: (result) => {
          settle(result, (sender) => {
            setSenderId(sender.senderId);
          });
        },
      },
    );
  };

  const submit = (event: SubmitEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (senderId === undefined) {
      return;
    }
    verify.mutate(
      { body: { code: draft.code }, params: { path: { senderId } } },
      {
        onSuccess: (result) => {
          settle(result, onClose);
        },
      },
    );
  };

  return (
    <Modal labelledBy={TITLE_ID} onClose={onClose}>
      <form onSubmit={submit}>
        <Modal.Header>
          <Modal.Title id={TITLE_ID}>{TITLE}</Modal.Title>
        </Modal.Header>
        <Modal.Body>
          <p className={styles.copy}>{COPY}</p>
          <AddOwnNumberFields
            codeSent={senderId !== undefined}
            draft={draft}
            onChange={setDraft}
            onSendCode={sendCode}
            sending={add.isPending}
          />
          <Toast
            notice={notice}
            onDismiss={() => {
              setNotice(undefined);
            }}
          />
        </Modal.Body>
        <Modal.Footer>
          <Button onClick={onClose} variant="secondary">
            {CANCEL_LABEL}
          </Button>
          <Button disabled={verify.isPending || !isVerificationCode(draft.code)} type="submit">
            {ADD_LABEL}
          </Button>
        </Modal.Footer>
      </form>
    </Modal>
  );
}
