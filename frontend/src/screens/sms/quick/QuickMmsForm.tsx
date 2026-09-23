import { Link } from "react-router";

import type { QuickFormProps } from "./QuickComposer";
import { SendTimeChoice } from "./SendTimeChoice";
import { SenderSelect } from "./SenderSelect";
import { MmsComposer } from "./composer/MmsComposer";
import { RecipientField } from "./recipients/RecipientField";

import styles from "./QuickMmsForm.module.css";

const COUNTRIES_LABEL = "See supported countries here";
const COUNTRIES_PATH = "/account/messaging";
const NOTICE_PREFIX = "MMS is not supported in all countries.";

export function QuickMmsForm({ draft, onNotice, onPatch, senders }: QuickFormProps) {
  return (
    <>
      <p className={styles.notice}>
        {NOTICE_PREFIX} <Link to={COUNTRIES_PATH}>{COUNTRIES_LABEL}</Link>
      </p>
      <RecipientField
        onChange={(recipients) => {
          onPatch({ recipients });
        }}
        onRefusal={onNotice}
        recipients={draft.recipients}
      />
      <SenderSelect
        onChange={(senderId) => {
          onPatch({ senderId });
        }}
        senders={senders}
        value={draft.senderId}
      />
      <MmsComposer
        body={draft.body}
        mediaKey={draft.mediaKey}
        onBodyChange={(body) => {
          onPatch({ body });
        }}
        onMediaChange={(mediaKey) => {
          onPatch({ mediaKey });
        }}
        onSubjectChange={(subject) => {
          onPatch({ subject });
        }}
        recipients={draft.recipients}
        subject={draft.subject}
      />
      <SendTimeChoice
        onChange={(sendAt) => {
          onPatch({ sendAt });
        }}
        sendAt={draft.sendAt}
      />
    </>
  );
}
