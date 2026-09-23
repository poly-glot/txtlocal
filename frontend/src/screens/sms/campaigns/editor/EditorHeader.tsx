import { useRef } from "react";

import { Button } from "@/components/Button/Button";
import { IconButton } from "@/components/IconButton/IconButton";

import styles from "./EditorHeader.module.css";

const BACK_LABEL = "Back to campaigns";
const EDIT_NAME_LABEL = "Edit name";
const NAME_ID = "campaign-name";
const NAME_LABEL = "Campaign name";
const NAME_PLACEHOLDER = "Campaign name...";
const SAVE_DRAFT_LABEL = "SAVE DRAFT";

interface Props {
  name: string;
  onBack: () => void;
  onNameChange: (name: string) => void;
  onSaveDraft: () => void;
}

export function EditorHeader({ name, onBack, onNameChange, onSaveDraft }: Props) {
  const field = useRef<HTMLInputElement>(null);

  return (
    <header className={styles.header}>
      <IconButton icon="back" label={BACK_LABEL} onClick={onBack} />
      <div className={styles.name}>
        <label className={styles.label} htmlFor={NAME_ID}>
          {NAME_LABEL}
        </label>
        <input
          className={styles.input}
          id={NAME_ID}
          onChange={(event) => {
            onNameChange(event.target.value);
          }}
          placeholder={NAME_PLACEHOLDER}
          ref={field}
          value={name}
        />
        <button
          className={styles.edit}
          onClick={() => {
            field.current?.focus();
          }}
          type="button"
        >
          {EDIT_NAME_LABEL}
        </button>
      </div>
      <Button onClick={onSaveDraft} variant="secondary">
        {SAVE_DRAFT_LABEL}
      </Button>
    </header>
  );
}
