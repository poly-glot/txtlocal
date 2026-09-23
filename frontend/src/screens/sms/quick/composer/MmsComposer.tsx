import { useMediaUpload } from "@/api/media";
import { Input } from "@/components/Input/Input";
import { MediaUpload } from "@/components/MediaUpload/MediaUpload";
import { MessageBody } from "@/components/MessageBody/MessageBody";

import type { Recipient } from "../rules";
import { hasNamedRecipient } from "../rules";
import { ComposerToolbar } from "./ComposerToolbar";
import { mmsCounterText } from "./rules";

const MESSAGE_LABEL = "Message";
const SUBJECT_LABEL = "Subject";
const SUBJECT_MAX = 40;

interface Props {
  body: string;
  mediaKey: string | null;
  onBodyChange: (body: string) => void;
  onMediaChange: (mediaKey: string | null) => void;
  onSubjectChange: (subject: string) => void;
  recipients: readonly Recipient[];
  subject: string;
}

export function MmsComposer({
  body,
  mediaKey,
  onBodyChange,
  onMediaChange,
  onSubjectChange,
  recipients,
  subject,
}: Props) {
  const upload = useMediaUpload();
  const toolbar = (
    <ComposerToolbar
      body={body}
      onBodyChange={onBodyChange}
      placeholdersEnabled={hasNamedRecipient(recipients)}
    />
  );

  return (
    <>
      <Input
        id="mms-subject"
        label={SUBJECT_LABEL}
        maxLength={SUBJECT_MAX}
        onChange={(event) => {
          onSubjectChange(event.target.value);
        }}
        placeholder={SUBJECT_LABEL}
        value={subject}
      />
      <MediaUpload mediaKey={mediaKey} onChange={onMediaChange} upload={upload} />
      <MessageBody
        id="mms-body"
        label={MESSAGE_LABEL}
        onChange={onBodyChange}
        toolbar={toolbar}
        value={body}
      >
        {mmsCounterText(body)}
      </MessageBody>
    </>
  );
}
