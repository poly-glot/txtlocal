import { useState } from "react";

import { Button } from "@/components/Button/Button";
import { Input } from "@/components/Input/Input";

import { looksLikeNumber } from "./rules";

import styles from "./NewNumberPrompt.module.css";

const CANCEL_LABEL = "Cancel";
const NUMBER_LABEL = "Mobile number";
const NUMBER_PLACEHOLDER = "+447400123123";
const START_LABEL = "Start";

interface Props {
  onCancel: () => void;
  onStart: (peer: string) => void;
}

export function NewNumberPrompt({ onCancel, onStart }: Props) {
  const [value, setValue] = useState("");

  return (
    <form
      className={styles.prompt}
      onSubmit={(event) => {
        event.preventDefault();
        if (looksLikeNumber(value)) {
          onStart(value.trim());
        }
      }}
    >
      <Input
        id="inbox-new-number"
        label={NUMBER_LABEL}
        onChange={(event) => {
          setValue(event.target.value);
        }}
        placeholder={NUMBER_PLACEHOLDER}
        type="tel"
        value={value}
      />
      <div className={styles.actions}>
        <Button disabled={!looksLikeNumber(value)} type="submit">
          {START_LABEL}
        </Button>
        <Button onClick={onCancel} type="button" variant="secondary">
          {CANCEL_LABEL}
        </Button>
      </div>
    </form>
  );
}
