import { useState } from "react";
import type { ReactNode, SubmitEvent } from "react";

import type { GeneralSettings } from "@/api/generated/dashboard";
import { useApiMutation } from "@/api/queries";
import { Button } from "@/components/Button/Button";
import { Toast } from "@/components/Toast/Toast";
import { noticeOf } from "@/lib/notice";
import type { Notice } from "@/types";

import { BalanceManagementFields } from "./BalanceManagementFields";
import { BillingContactFields } from "./BillingContactFields";

import styles from "./GeneralForm.module.css";

const BALANCE_TITLE = "Balance Management";
const CONTACT_TITLE = "Billing Contact";
const SAVED_MSG = "Settings saved.";
const SAVE_LABEL = "Save";

interface Props {
  initial: GeneralSettings;
}

interface SectionProps {
  children: ReactNode;
  title: string;
}

export function GeneralForm({ initial }: Props) {
  const [draft, setDraft] = useState<GeneralSettings>(initial);
  const [notice, setNotice] = useState<Notice>();
  const save = useApiMutation("put", "/api/app/billing/general");

  const change = (patch: Partial<GeneralSettings>) => {
    setDraft({ ...draft, ...patch });
  };

  const submit = (event: SubmitEvent<HTMLFormElement>) => {
    event.preventDefault();
    save.mutate(
      { body: draft },
      {
        onSuccess: (result) => {
          setNotice(noticeOf(result, SAVED_MSG));
        },
      },
    );
  };

  return (
    <form className={styles.form} onSubmit={submit}>
      <Section title={CONTACT_TITLE}>
        <BillingContactFields draft={draft} onChange={change} />
      </Section>
      <Section title={BALANCE_TITLE}>
        <BalanceManagementFields draft={draft} onChange={change} saved={initial} />
      </Section>
      <Toast
        notice={notice}
        onDismiss={() => {
          setNotice(undefined);
        }}
      />
      <div className={styles.actions}>
        <Button disabled={save.isPending} type="submit">
          {SAVE_LABEL}
        </Button>
      </div>
    </form>
  );
}

function Section({ children, title }: SectionProps) {
  return (
    <details className={styles.section} open>
      <summary className={styles.title}>{title}</summary>
      {children}
    </details>
  );
}
