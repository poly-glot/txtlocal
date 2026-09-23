import { useApiMutation, useApiQuery } from "@/api/queries";
import { Button } from "@/components/Button/Button";
import { Modal } from "@/components/Modal/Modal";
import { noticeOf } from "@/lib/notice";
import type { Notice } from "@/types";

import { QuoteSummary } from "./QuoteSummary";
import type { Draft } from "./rules";
import { confirmSendTitle, quickSendRequest } from "./rules";

const CLOSE_LABEL = "CLOSE";
const SEND_LABEL = "SEND";
const SENT_MSG = "Your message is on its way.";
const TITLE_ID = "confirm-send-title";

interface Props {
  draft: Draft;
  onClose: () => void;
  onSent: (notice: Notice) => void;
  timezone: string | undefined;
}

export function ConfirmSendModal({ draft, onClose, onSent, timezone }: Props) {
  const input = quickSendRequest(draft);
  const quote = useApiQuery("post", "/api/app/messages/quote", { body: input });
  const send = useApiMutation("post", "/api/app/messages/send");

  const submit = () => {
    send.mutate(
      { body: input },
      {
        onSuccess: (result) => {
          onSent(noticeOf(result, SENT_MSG));
        },
      },
    );
  };

  return (
    <Modal labelledBy={TITLE_ID} onClose={onClose}>
      <Modal.Header>
        <Modal.Title id={TITLE_ID}>{confirmSendTitle(draft.kind)}</Modal.Title>
      </Modal.Header>
      <Modal.Body>
        <QuoteSummary quote={quote.data} sendAt={draft.sendAt} timezone={timezone} />
      </Modal.Body>
      <Modal.Footer>
        <Button onClick={onClose} variant="secondary">
          {CLOSE_LABEL}
        </Button>
        <Button disabled={quote.data?.status !== "OK" || send.isPending} onClick={submit}>
          {SEND_LABEL}
        </Button>
      </Modal.Footer>
    </Modal>
  );
}
