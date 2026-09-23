import { useState } from "react";
import type { SubmitEvent } from "react";

import type { MessagingSettings } from "@/api/generated/dashboard";
import { useApiMutation } from "@/api/queries";
import { Select } from "@/components/Select/Select";
import { Toast } from "@/components/Toast/Toast";
import { noticeOf } from "@/lib/notice";
import { COUNTRY_CODES } from "@/rules/countries";
import type { Notice } from "@/types";

import { countryOptions } from "../rules";
import { FromOptions } from "./FromOptions";
import { SettingsSectionForm } from "./SettingsSectionForm";
import { UnicodeChoice } from "./UnicodeChoice";
import { partsOptions } from "./rules";

import styles from "./MessagingSettingsForm.module.css";

const CHARACTER_LIMIT_TITLE = "Character Limit";
const COUNTRIES = countryOptions(COUNTRY_CODES);
const DEFAULT_COUNTRY_INFO =
  "If the recipient phone number isn't formatted in international format, we'll automatically format it for you. This will use the country below.";
const DEFAULT_COUNTRY_TITLE = "Default Country Code";
const FROM_OPTIONS_TITLE = "From Options";
const MAX_PARTS_LABEL = "Max number of message parts:";
const PARTS = partsOptions();
const SAVED_MSG = "Settings saved.";
const UNICODE_TITLE = "Unicode";

interface Props {
  initial: MessagingSettings;
}

export function MessagingSettingsForm({ initial }: Props) {
  const [settings, setSettings] = useState(initial);
  const [notice, setNotice] = useState<Notice>();
  const save = useApiMutation("put", "/api/app/account/settings/messaging");

  const submit = (event: SubmitEvent<HTMLFormElement>) => {
    event.preventDefault();
    save.mutate(
      { body: settings },
      {
        onSuccess: (result) => {
          setNotice(noticeOf(result, SAVED_MSG));
        },
      },
    );
  };

  return (
    <div className={styles.sections}>
      <Toast
        notice={notice}
        onDismiss={() => {
          setNotice(undefined);
        }}
      />
      <SettingsSectionForm onSubmit={submit} saving={save.isPending} title={FROM_OPTIONS_TITLE}>
        <FromOptions onChange={setSettings} settings={settings} />
      </SettingsSectionForm>
      <SettingsSectionForm onSubmit={submit} saving={save.isPending} title={CHARACTER_LIMIT_TITLE}>
        <Select
          id="max-parts"
          label={MAX_PARTS_LABEL}
          onChange={(event) => {
            setSettings({ ...settings, maxParts: Number(event.target.value) });
          }}
          options={PARTS}
          value={String(settings.maxParts)}
        />
      </SettingsSectionForm>
      <SettingsSectionForm onSubmit={submit} saving={save.isPending} title={UNICODE_TITLE}>
        <UnicodeChoice
          onChange={(unicodeMode) => {
            setSettings({ ...settings, unicodeMode });
          }}
          value={settings.unicodeMode}
        />
      </SettingsSectionForm>
      <SettingsSectionForm onSubmit={submit} saving={save.isPending} title={DEFAULT_COUNTRY_TITLE}>
        <p className={styles.info}>{DEFAULT_COUNTRY_INFO}</p>
        <Select
          id="messaging-default-country"
          label={DEFAULT_COUNTRY_TITLE}
          onChange={(event) => {
            setSettings({ ...settings, defaultCountry: event.target.value });
          }}
          options={COUNTRIES}
          value={settings.defaultCountry}
        />
      </SettingsSectionForm>
    </div>
  );
}
