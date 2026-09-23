import type { QuickFormProps } from "./QuickComposer";
import { SendTimeChoice } from "./SendTimeChoice";
import { SenderSelect } from "./SenderSelect";
import { MessageComposer } from "./composer/MessageComposer";
import { RecipientField } from "./recipients/RecipientField";
import { hasNamedRecipient } from "./rules";

export function QuickSmsForm({ draft, onNotice, onPatch, senders }: QuickFormProps) {
  return (
    <>
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
      <MessageComposer
        body={draft.body}
        onBodyChange={(body) => {
          onPatch({ body });
        }}
        onShortenUrlsChange={(shortenUrls) => {
          onPatch({ shortenUrls });
        }}
        placeholdersEnabled={hasNamedRecipient(draft.recipients)}
        shortenUrls={draft.shortenUrls}
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
