import { useState } from "react";

import type { CampaignQuote } from "@/api/generated/dashboard";

import { ConfirmCampaignModal } from "./ConfirmCampaignModal";
import { SendNowButton } from "./SendNowButton";

import styles from "./ScheduleActions.module.css";

interface Props {
  campaignId: string | undefined;
  name: string;
  onScheduled: () => void;
  quote: CampaignQuote | undefined;
}

export function ScheduleActions({ campaignId, name, onScheduled, quote }: Props) {
  const [sendAt, setSendAt] = useState<string>();

  return (
    <footer className={styles.foot}>
      <SendNowButton
        disabled={campaignId === undefined || quote === undefined}
        onChoose={setSendAt}
      />
      {campaignId !== undefined && quote !== undefined && sendAt !== undefined ? (
        <ConfirmCampaignModal
          campaignId={campaignId}
          name={name}
          onClose={() => {
            setSendAt(undefined);
          }}
          onScheduled={onScheduled}
          quote={quote}
          sendAt={sendAt}
        />
      ) : null}
    </footer>
  );
}
