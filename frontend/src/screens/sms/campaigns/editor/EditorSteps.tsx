import type { CampaignDraft, SendersView } from "@/api/generated/dashboard";
import { PhonePreview } from "@/components/PhonePreview/PhonePreview";

import type { ScreenProduct } from "../../rules";
import { MessageStep } from "./steps/MessageStep";
import { RecipientsStep } from "./steps/RecipientsStep";
import { SenderStep } from "./steps/SenderStep";

import styles from "./EditorSteps.module.css";

const PREVIEW_CAPTION =
  "Placeholders will be replaced for all contacts in a list. This is an example of the first contact.";
const PREVIEW_TITLE = "REPLY NUM";

interface Props {
  draft: CampaignDraft;
  onNext: () => void;
  onPatch: (change: Partial<CampaignDraft>) => void;
  product: ScreenProduct;
  senders: SendersView;
}

export function EditorSteps({ draft, onNext, onPatch, product, senders }: Props) {
  return (
    <div className={styles.columns}>
      <div className={styles.steps}>
        <RecipientsStep
          listId={draft.listId ?? ""}
          onChange={(listId) => {
            onPatch({ listId });
          }}
        />
        <SenderStep
          onChange={(senderId) => {
            onPatch({ senderId });
          }}
          product={product}
          senderId={draft.senderId}
          senders={senders}
        />
        <MessageStep draft={draft} onNext={onNext} onPatch={onPatch} product={product} />
      </div>
      <PhonePreview
        body={draft.body}
        caption={PREVIEW_CAPTION}
        footer={draft.footer}
        title={PREVIEW_TITLE}
      />
    </div>
  );
}
