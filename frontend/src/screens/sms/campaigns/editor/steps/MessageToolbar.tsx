import { useApiQuery } from "@/api/queries";
import type { Option } from "@/components/Select/Select";
import { dataOf } from "@/lib/format";

import { InsertPicker } from "./InsertPicker";

import styles from "./MessageToolbar.module.css";

const EMOJI_ITEMS: readonly Option[] = ["😀", "👍", "🎉", "❤️", "✅"].map((emoji) => ({
  label: emoji,
  value: emoji,
}));
const EMOJI_LABEL = "Emoji";
const PLACEHOLDER_ITEMS: readonly Option[] = [
  "{first_name}",
  "{last_name}",
  "{mobile}",
  "{email}",
  "{cf1}",
  "{cf2}",
  "{cf3}",
  "{cf4}",
].map((placeholder) => ({ label: placeholder, value: placeholder }));
const PLACEHOLDER_LABEL = "Placeholder";
const REPLACE_BODY_MSG = "Replace the message with this template?";
const SHORT_URL_ID = "campaign-short-url";
const SHORT_URL_LABEL = "Short URL";
const TEMPLATE_LABEL = "Template";

interface Props {
  body: string;
  onBodyChange: (body: string) => void;
  onShortenUrlsChange: (shortenUrls: boolean) => void;
  shortenUrls: boolean;
}

export function MessageToolbar({ body, onBodyChange, onShortenUrlsChange, shortenUrls }: Props) {
  const templates = useApiQuery("get", "/api/app/templates");
  const items = dataOf(templates.data, []).map((template) => ({
    label: template.name,
    value: template.body,
  }));

  const replaceBody = (chosen: string) => {
    if (body === "" || window.confirm(REPLACE_BODY_MSG)) {
      onBodyChange(chosen);
    }
  };

  return (
    <div className={styles.toolbar}>
      <InsertPicker
        items={PLACEHOLDER_ITEMS}
        label={PLACEHOLDER_LABEL}
        onPick={(placeholder) => {
          onBodyChange(`${body}${placeholder}`);
        }}
      />
      <InsertPicker
        disabled={items.length === 0}
        items={items}
        label={TEMPLATE_LABEL}
        onPick={replaceBody}
      />
      <div className={styles.shorten}>
        <input
          checked={shortenUrls}
          id={SHORT_URL_ID}
          onChange={(event) => {
            onShortenUrlsChange(event.target.checked);
          }}
          type="checkbox"
        />
        <label className={styles.toggle} htmlFor={SHORT_URL_ID}>
          {SHORT_URL_LABEL}
        </label>
      </div>
      <InsertPicker
        items={EMOJI_ITEMS}
        label={EMOJI_LABEL}
        onPick={(emoji) => {
          onBodyChange(`${body}${emoji}`);
        }}
      />
    </div>
  );
}
