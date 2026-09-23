import { useState } from "react";

import { Button } from "@/components/Button/Button";
import { Input } from "@/components/Input/Input";
import { Modal } from "@/components/Modal/Modal";

import styles from "./ApiKeyModal.module.css";

const COPIED_LABEL = "Copied";
const COPY_LABEL = "Copy";
const DONE_LABEL = "Done";
const KEY_LABEL = "API key";
const STORE_MSG = "Store this key now. For your security we cannot show it again.";
const TITLE = "Your new API key";
const TITLE_ID = "api-key-title";

interface Props {
  apiKey: string;
  onDone: () => void;
}

export function ApiKeyModal({ apiKey, onDone }: Props) {
  const [copied, setCopied] = useState(false);

  const copy = () => {
    void navigator.clipboard.writeText(apiKey).then(() => {
      setCopied(true);
    });
  };

  return (
    <Modal labelledBy={TITLE_ID} onClose={onDone}>
      <Modal.Header>
        <Modal.Title id={TITLE_ID}>{TITLE}</Modal.Title>
      </Modal.Header>
      <Modal.Body>
        <Input id="api-key" label={KEY_LABEL} readOnly value={apiKey} />
        <p className={styles.note}>{STORE_MSG}</p>
      </Modal.Body>
      <Modal.Footer>
        <Button onClick={copy} variant="secondary">
          {copied ? COPIED_LABEL : COPY_LABEL}
        </Button>
        <Button onClick={onDone}>{DONE_LABEL}</Button>
      </Modal.Footer>
    </Modal>
  );
}
