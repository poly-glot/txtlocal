import type { Campaign } from "@/api/generated/dashboard";
import { RowAction } from "@/components/RowAction/RowAction";

import styles from "./CampaignRowActions.module.css";

const CANCEL_LABEL = "Cancel";
const DUPLICATE_LABEL = "Duplicate";
const OPEN_LABEL = "Open";

const actionName = (action: string, name: string) => `${action} ${name}`;

interface Props {
  campaign: Campaign;
  onCancel: (campaign: Campaign) => void;
  onDuplicate: (campaign: Campaign) => void;
  onOpen: (campaign: Campaign) => void;
}

export function CampaignRowActions({ campaign, onCancel, onDuplicate, onOpen }: Props) {
  return (
    <span className={styles.actions}>
      <RowAction
        aria-label={actionName(OPEN_LABEL, campaign.name)}
        onClick={() => {
          onOpen(campaign);
        }}
      >
        {OPEN_LABEL}
      </RowAction>
      {campaign.status === "SCHEDULED" ? (
        <RowAction
          aria-label={actionName(CANCEL_LABEL, campaign.name)}
          onClick={() => {
            onCancel(campaign);
          }}
          tone="danger"
        >
          {CANCEL_LABEL}
        </RowAction>
      ) : null}
      <RowAction
        aria-label={actionName(DUPLICATE_LABEL, campaign.name)}
        onClick={() => {
          onDuplicate(campaign);
        }}
      >
        {DUPLICATE_LABEL}
      </RowAction>
    </span>
  );
}
