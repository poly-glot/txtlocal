import { useId, useState } from "react";

import { Button } from "@/components/Button/Button";
import { Modal } from "@/components/Modal/Modal";
import { Toast } from "@/components/Toast/Toast";
import type { Notice, Result } from "@/types";

import styles from "./ConfirmDeleteModal.module.css";

const CANCEL_LABEL = "Cancel";
const DELETE_LABEL = "Delete";

interface Removal {
  onSuccess: (result: Result<unknown>) => void;
}

interface Props {
  onCancel: () => void;
  onDeleted: () => void;
  pending: boolean;
  question: string;
  remove: (removal: Removal) => void;
  title: string;
}

export function ConfirmDeleteModal({
  onCancel,
  onDeleted,
  pending,
  question,
  remove,
  title,
}: Props) {
  const titleId = useId();
  const [notice, setNotice] = useState<Notice>();

  const confirm = () => {
    remove({
      onSuccess: (result) => {
        if (result.status === "ERROR") {
          setNotice({ message: result.message, tone: "error" });
          return;
        }
        onDeleted();
      },
    });
  };

  return (
    <Modal labelledBy={titleId} onClose={onCancel}>
      <Modal.Header>
        <Modal.Title id={titleId}>{title}</Modal.Title>
      </Modal.Header>
      <Modal.Body>
        <p className={styles.question}>{question}</p>
        <Toast
          notice={notice}
          onDismiss={() => {
            setNotice(undefined);
          }}
        />
      </Modal.Body>
      <Modal.Footer>
        <Button onClick={onCancel} variant="secondary">
          {CANCEL_LABEL}
        </Button>
        <Button disabled={pending} onClick={confirm} variant="danger">
          {DELETE_LABEL}
        </Button>
      </Modal.Footer>
    </Modal>
  );
}
