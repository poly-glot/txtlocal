import type { ReactNode, SubmitEvent } from "react";

import { Button } from "@/components/Button/Button";
import { Section } from "@/components/Section/Section";

import styles from "./SettingsSectionForm.module.css";

const SAVE_LABEL = "Save";

interface Props {
  children: ReactNode;
  onSubmit: (event: SubmitEvent<HTMLFormElement>) => void;
  saving: boolean;
  title: string;
}

export function SettingsSectionForm({ children, onSubmit, saving, title }: Props) {
  return (
    <form aria-label={title} className={styles.form} onSubmit={onSubmit}>
      <Section title={title}>
        {children}
        <div className={styles.actions}>
          <Button disabled={saving} type="submit">
            {SAVE_LABEL}
          </Button>
        </div>
      </Section>
    </form>
  );
}
