import { useState } from "react";

import type { UserRow } from "@/api/generated/dashboard";
import { useApiMutation } from "@/api/queries";
import { Button } from "@/components/Button/Button";
import { Modal } from "@/components/Modal/Modal";
import { Toast } from "@/components/Toast/Toast";
import type { Notice } from "@/types";

import styles from "./RegenerateKeyModal.module.css";

const CANCEL_LABEL = "CANCEL";
const CONFIRM_LABEL = "REGENERATE";
const TITLE = "Regenerate API key";
const TITLE_ID = "regenerate-key-title";

const question = (username: string) =>
  `Regenerate the API key for ${username}? Integrations using the current key will stop working.`;

interface Props {
  onClose: () => void;
  onRegenerated: (apiKey: string) => void;
  user: UserRow;
}

export function RegenerateKeyModal({ onClose, onRegenerated, user }: Props) {
  const [notice, setNotice] = useState<Notice>();
  const regenerate = useApiMutation("post", "/api/app/account/users/{userId}/api-key");

  const confirm = () => {
    regenerate.mutate(
      { params: { path: { userId: user.userId } } },
      {
        onSuccess: (result) => {
          if (result.status === "OK") {
            onRegenerated(result.data.apiKey);
            return;
          }
          setNotice({ message: result.message, tone: "error" });
        },
      },
    );
  };

  return (
    <Modal labelledBy={TITLE_ID} onClose={onClose}>
      <Modal.Header>
        <Modal.Title id={TITLE_ID}>{TITLE}</Modal.Title>
      </Modal.Header>
      <Modal.Body>
        <p className={styles.question}>{question(user.username)}</p>
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
        <Button disabled={regenerate.isPending} onClick={confirm} variant="danger">
          {CONFIRM_LABEL}
        </Button>
      </Modal.Footer>
    </Modal>
  );
}
