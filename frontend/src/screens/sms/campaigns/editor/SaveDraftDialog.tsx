import { Button } from "@/components/Button/Button";
import { IconButton } from "@/components/IconButton/IconButton";
import { Modal } from "@/components/Modal/Modal";

import styles from "./SaveDraftDialog.module.css";

const BODY = "Come back to finalize and send your campaign later.";
const CLOSE_LABEL = "Close";
const DISCARD_LABEL = "DISCARD DRAFT";
const SAVE_LABEL = "SAVE DRAFT";
const TITLE = "Save as a draft?";
const TITLE_ID = "campaign-save-draft-title";

interface Props {
  onClose: () => void;
  onDiscard: () => void;
  onSave: () => void;
}

export function SaveDraftDialog({ onClose, onDiscard, onSave }: Props) {
  return (
    <Modal labelledBy={TITLE_ID} onClose={onClose}>
      <Modal.Header>
        <div className={styles.row}>
          <Modal.Title id={TITLE_ID}>{TITLE}</Modal.Title>
          <IconButton icon="close" label={CLOSE_LABEL} onClick={onClose} />
        </div>
      </Modal.Header>
      <Modal.Body>
        <p className={styles.body}>{BODY}</p>
      </Modal.Body>
      <Modal.Footer>
        <Button onClick={onDiscard} variant="danger">
          {DISCARD_LABEL}
        </Button>
        <Button onClick={onSave}>{SAVE_LABEL}</Button>
      </Modal.Footer>
    </Modal>
  );
}
