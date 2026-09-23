import type { CampaignQuote } from "@/api/generated/dashboard";
import { useApiMutation } from "@/api/queries";
import { Button } from "@/components/Button/Button";
import { Modal } from "@/components/Modal/Modal";
import { useAccountTimezone } from "@/lib/useAccountTimezone";

import { QuoteSummary } from "./QuoteSummary";
import { scheduleRequestOf } from "./rules";

import styles from "./ConfirmCampaignModal.module.css";

const CLOSE_LABEL = "CLOSE";
const SCHEDULE_LABEL = "SCHEDULE";
const SEND_LABEL = "SEND";
const TITLE_ID = "campaign-confirm-title";

interface Props {
  campaignId: string;
  name: string;
  onClose: () => void;
  onScheduled: () => void;
  quote: CampaignQuote;
  sendAt: string;
}

export function ConfirmCampaignModal({
  campaignId,
  name,
  onClose,
  onScheduled,
  quote,
  sendAt,
}: Props) {
  const schedule = useApiMutation("post", "/api/app/campaigns/{campaignId}/schedule");
  const timezone = useAccountTimezone();
  const refusal = schedule.data?.status === "ERROR" ? schedule.data.message : undefined;

  const submit = () => {
    schedule.mutate(
      { body: scheduleRequestOf(sendAt), params: { path: { campaignId } } },
      {
        onSuccess: (result) => {
          if (result.status === "OK") {
            onScheduled();
          }
        },
      },
    );
  };

  return (
    <Modal labelledBy={TITLE_ID} onClose={onClose}>
      <Modal.Header>
        <Modal.Title id={TITLE_ID}>{name}</Modal.Title>
      </Modal.Header>
      <Modal.Body>
        <QuoteSummary quote={quote} sendAt={sendAt} timezone={timezone} />
        {refusal === undefined ? null : (
          <p className={styles.refusal} role="alert">
            {refusal}
          </p>
        )}
      </Modal.Body>
      <Modal.Footer>
        <Button onClick={onClose} variant="secondary">
          {CLOSE_LABEL}
        </Button>
        <Button disabled={schedule.isPending} onClick={submit}>
          {sendAt === "" ? SEND_LABEL : SCHEDULE_LABEL}
        </Button>
      </Modal.Footer>
    </Modal>
  );
}
