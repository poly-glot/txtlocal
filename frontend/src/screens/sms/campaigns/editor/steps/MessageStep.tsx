import type { CampaignDraft } from "@/api/generated/dashboard";
import { useMediaUpload } from "@/api/media";
import { Button } from "@/components/Button/Button";
import { Input } from "@/components/Input/Input";
import { MediaUpload } from "@/components/MediaUpload/MediaUpload";

import type { ScreenProduct } from "../../../rules";
import { MessageToolbar } from "./MessageToolbar";
import { OptOutChoice } from "./OptOutChoice";
import { StepSection } from "./StepSection";
import { contentTitle, counterText, footerFor, isMessageComplete } from "./rules";

import styles from "./MessageStep.module.css";

const BODY_ID = "campaign-body";
const CUSTOM_FIELDS_NOTE = "Custom fields are calculated and final count shown on confirmation.";
const NEXT_LABEL = "NEXT";
const STEP = 3;
const SUBJECT_LABEL = "Subject";
const TITLE = "Message";

interface Props {
  draft: CampaignDraft;
  onNext: () => void;
  onPatch: (change: Partial<CampaignDraft>) => void;
  product: ScreenProduct;
}

export function MessageStep({ draft, onNext, onPatch, product }: Props) {
  const upload = useMediaUpload();

  return (
    <StepSection
      complete={isMessageComplete(draft, product)}
      step={STEP}
      subtitle={contentTitle(product)}
      title={TITLE}
    >
      <MessageToolbar
        body={draft.body}
        onBodyChange={(body) => {
          onPatch({ body });
        }}
        onShortenUrlsChange={(shortenUrls) => {
          onPatch({ shortenUrls });
        }}
        shortenUrls={draft.shortenUrls}
      />
      {product === "MMS" ? (
        <>
          <Input
            id="campaign-subject"
            label={SUBJECT_LABEL}
            onChange={(event) => {
              onPatch({ subject: event.target.value });
            }}
            value={draft.subject ?? ""}
          />
          <MediaUpload
            mediaKey={draft.mediaKey ?? null}
            onChange={(mediaKey) => {
              onPatch({ mediaKey });
            }}
            upload={upload}
          />
        </>
      ) : null}
      <div className={styles.field}>
        <label className={styles.label} htmlFor={BODY_ID}>
          {contentTitle(product)}
        </label>
        <textarea
          className={styles.textarea}
          id={BODY_ID}
          onChange={(event) => {
            onPatch({ body: event.target.value });
          }}
          rows={8}
          value={draft.body}
        />
        <p className={styles.counter}>{counterText(draft, product)}</p>
        <p className={styles.note}>{CUSTOM_FIELDS_NOTE}</p>
      </div>
      <OptOutChoice
        footer={draft.footer}
        mode={draft.optOutMode}
        onFooterChange={(footer) => {
          onPatch({ footer });
        }}
        onModeChange={(optOutMode) => {
          onPatch({ footer: footerFor(optOutMode), optOutMode });
        }}
      />
      <div className={styles.actions}>
        <Button onClick={onNext}>{NEXT_LABEL}</Button>
      </div>
    </StepSection>
  );
}
