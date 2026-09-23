import { useApiQuery } from "@/api/queries";
import { ActionMenu } from "@/components/ActionMenu/ActionMenu";
import type { MenuItem } from "@/components/ActionMenu/ActionMenu";
import { dataOf } from "@/lib/format";

import styles from "./ComposerToolbar.module.css";

const EMOJI_LABEL = "Emoji";
const EMOJI_ITEMS: readonly MenuItem[] = ["😀", "👍", "🎉", "❤️", "✅"].map((emoji) => ({
  label: emoji,
  value: emoji,
}));
const PLACEHOLDER_LABEL = "Placeholder";
const PLACEHOLDER_ITEMS: readonly MenuItem[] = [
  "{first_name}",
  "{last_name}",
  "{mobile}",
  "{email}",
  "{cf1}",
  "{cf2}",
  "{cf3}",
  "{cf4}",
].map((placeholder) => ({ label: placeholder, value: placeholder }));
const REPLACE_BODY_MSG = "Replace the message with this template?";
const TEMPLATE_LABEL = "Template";

interface Props {
  body: string;
  onBodyChange: (body: string) => void;
  placeholdersEnabled: boolean;
}

export function ComposerToolbar({ body, onBodyChange, placeholdersEnabled }: Props) {
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
      <ActionMenu
        align="start"
        disabled={!placeholdersEnabled}
        items={PLACEHOLDER_ITEMS}
        label={PLACEHOLDER_LABEL}
        onPick={(placeholder) => {
          onBodyChange(`${body}${placeholder}`);
        }}
      />
      <ActionMenu
        align="start"
        disabled={items.length === 0}
        items={items}
        label={TEMPLATE_LABEL}
        onPick={replaceBody}
      />
      <ActionMenu
        align="start"
        items={EMOJI_ITEMS}
        label={EMOJI_LABEL}
        onPick={(emoji) => {
          onBodyChange(`${body}${emoji}`);
        }}
      />
    </div>
  );
}
