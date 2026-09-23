import { useApiQuery } from "@/api/queries";
import { Button } from "@/components/Button/Button";
import { Modal } from "@/components/Modal/Modal";

import { MessageFields } from "./MessageFields";

const CLOSE_LABEL = "CLOSE";
const TITLE = "Message detail";
const TITLE_ID = "message-detail-title";

interface Props {
  messageId: string;
  onClose: () => void;
  timezone: string | undefined;
}

export function MessageDrawer({ messageId, onClose, timezone }: Props) {
  const message = useApiQuery("get", "/api/app/messages/{messageId}", {
    params: { path: { messageId: messageId } },
  });

  return (
    <Modal labelledBy={TITLE_ID} onClose={onClose}>
      <Modal.Header>
        <Modal.Title id={TITLE_ID}>{TITLE}</Modal.Title>
      </Modal.Header>
      <Modal.Body>
        <MessageFields message={message.data} timezone={timezone} />
      </Modal.Body>
      <Modal.Footer>
        <Button onClick={onClose} variant="secondary">
          {CLOSE_LABEL}
        </Button>
      </Modal.Footer>
    </Modal>
  );
}
