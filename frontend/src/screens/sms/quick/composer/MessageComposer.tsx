import { Badge } from "@/components/Badge/Badge";
import { Icon } from "@/components/Icon/Icon";
import { MessageBody } from "@/components/MessageBody/MessageBody";
import { segmentSummary, segmentsOf } from "@/rules/segments";

import { ComposerToolbar } from "./ComposerToolbar";

import styles from "./MessageComposer.module.css";

const MESSAGE_LABEL = "Message";
const NEW_BADGE = "NEW";
const SHORTEN_LABEL = "Shorten my URL";

interface Props {
  body: string;
  onBodyChange: (body: string) => void;
  onShortenUrlsChange: (shortenUrls: boolean) => void;
  placeholdersEnabled: boolean;
  shortenUrls: boolean;
}

export function MessageComposer({
  body,
  onBodyChange,
  onShortenUrlsChange,
  placeholdersEnabled,
  shortenUrls,
}: Props) {
  const toolbar = (
    <ComposerToolbar
      body={body}
      onBodyChange={onBodyChange}
      placeholdersEnabled={placeholdersEnabled}
    />
  );

  return (
    <div className={styles.composer}>
      <MessageBody
        id="quick-body"
        label={MESSAGE_LABEL}
        onChange={onBodyChange}
        toolbar={toolbar}
        value={body}
      >
        {segmentSummary(segmentsOf(body))} <Icon name="info" size={14} />
      </MessageBody>
      <div className={styles.shorten}>
        <input
          checked={shortenUrls}
          id="quick-shorten"
          onChange={(event) => {
            onShortenUrlsChange(event.target.checked);
          }}
          type="checkbox"
        />
        <label className={styles.toggle} htmlFor="quick-shorten">
          {SHORTEN_LABEL}
        </label>
        <Badge tone="success">{NEW_BADGE}</Badge>
      </div>
    </div>
  );
}
