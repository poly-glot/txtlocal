import { useState } from "react";

import { Button } from "@/components/Button/Button";
import { Input } from "@/components/Input/Input";
import { Modal } from "@/components/Modal/Modal";

const COPIED_LABEL = "Copied";
const COPY_LABEL = "Copy";
const DONE_LABEL = "Done";
const SECRET_LABEL = "Signing secret";
const STORE_MSG =
  "Store this secret now. It signs every webhook delivery for this rule and we cannot show it again.";
const TITLE = "Delivery rule created";
const TITLE_ID = "delivery-secret-title";

interface Props {
  onDone: () => void;
  secret: string;
}

export function DeliverySecretModal({ onDone, secret }: Props) {
  const [copied, setCopied] = useState(false);

  const copy = () => {
    void navigator.clipboard.writeText(secret).then(() => {
      setCopied(true);
    });
  };

  return (
    <Modal labelledBy={TITLE_ID} onClose={onDone}>
      <Modal.Header>
        <Modal.Title id={TITLE_ID}>{TITLE}</Modal.Title>
      </Modal.Header>
      <Modal.Body>
        <Input
          helper={STORE_MSG}
          id="delivery-rule-secret"
          label={SECRET_LABEL}
          readOnly
          value={secret}
        />
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
