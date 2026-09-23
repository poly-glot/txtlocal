import { useState } from "react";
import type { ChangeEvent, SubmitEvent } from "react";

import type { MeView } from "@/api/generated/dashboard";
import { useApiMutation } from "@/api/queries";
import { Button } from "@/components/Button/Button";
import { Input } from "@/components/Input/Input";
import { Section } from "@/components/Section/Section";
import { Toast } from "@/components/Toast/Toast";
import { noticeOf } from "@/lib/notice";
import type { Notice } from "@/types";

import type { ProfileDraft } from "./rules";
import { toProfileUpdate } from "./rules";

import styles from "./ProfileForm.module.css";

const CONTACT_TITLE = "Contact";
const FIRST_NAME_LABEL = "First Name";
const LAST_NAME_LABEL = "Last Name";
const NAME_MAX_CHARS = 50;
const NAME_TITLE = "Name";
const PHONE_LABEL = "Phone";
const SAVED_MSG = "Profile saved.";
const SAVE_LABEL = "Save";
const USERNAME_LABEL = "Username / Email";

interface Props {
  me: MeView;
}

export function ProfileForm({ me }: Props) {
  const [draft, setDraft] = useState<ProfileDraft>({
    firstName: me.firstName,
    lastName: me.lastName,
    phone: me.phone ?? "",
  });
  const [notice, setNotice] = useState<Notice>();
  const save = useApiMutation("patch", "/api/app/me/profile");

  const update = (field: keyof ProfileDraft) => (event: ChangeEvent<HTMLInputElement>) => {
    setDraft({ ...draft, [field]: event.target.value });
  };

  const submit = (event: SubmitEvent<HTMLFormElement>) => {
    event.preventDefault();
    save.mutate(
      { body: toProfileUpdate(draft) },
      {
        onSuccess: (result) => {
          setNotice(noticeOf(result, SAVED_MSG));
        },
      },
    );
  };

  return (
    <form className={styles.form} onSubmit={submit}>
      <Section title={NAME_TITLE}>
        <div className={styles.fields}>
          <Input
            id="first-name"
            label={FIRST_NAME_LABEL}
            maxLength={NAME_MAX_CHARS}
            onChange={update("firstName")}
            required
            value={draft.firstName}
          />
          <Input
            id="last-name"
            label={LAST_NAME_LABEL}
            maxLength={NAME_MAX_CHARS}
            onChange={update("lastName")}
            required
            value={draft.lastName}
          />
        </div>
      </Section>
      <Section title={CONTACT_TITLE}>
        <div className={styles.fields}>
          <Input disabled id="username" label={USERNAME_LABEL} value={me.username} />
          <Input
            id="phone"
            label={PHONE_LABEL}
            onChange={update("phone")}
            type="tel"
            value={draft.phone}
          />
        </div>
      </Section>
      <Toast
        notice={notice}
        onDismiss={() => {
          setNotice(undefined);
        }}
      />
      <div className={styles.footer}>
        <Button disabled={save.isPending} type="submit">
          {SAVE_LABEL}
        </Button>
      </div>
    </form>
  );
}
