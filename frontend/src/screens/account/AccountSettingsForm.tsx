import { useState } from "react";
import type { SubmitEvent } from "react";

import type { AccountSettings } from "@/api/generated/dashboard";
import { useApiMutation } from "@/api/queries";
import { Button } from "@/components/Button/Button";
import { Input } from "@/components/Input/Input";
import { Section } from "@/components/Section/Section";
import { Select } from "@/components/Select/Select";
import { Toast } from "@/components/Toast/Toast";
import { noticeOf } from "@/lib/notice";
import { COUNTRY_CODES } from "@/rules/countries";
import type { Notice } from "@/types";

import { countryOptions } from "./rules";

import styles from "./AccountSettingsForm.module.css";

const ACCOUNT_TITLE = "Account";
const COUNTRIES = countryOptions(COUNTRY_CODES);
const COUNTRY_LABEL = "Default Country Code";
const NAME_LABEL = "Account Name";
const REGION_TITLE = "Region";
const SAVED_MSG = "Settings saved.";
const SAVE_LABEL = "Save";
const TIMEZONE_LABEL = "Timezone";
const TIMEZONES = Intl.supportedValuesOf("timeZone");

interface Props {
  initial: AccountSettings;
}

export function AccountSettingsForm({ initial }: Props) {
  const [settings, setSettings] = useState(initial);
  const [notice, setNotice] = useState<Notice>();
  const save = useApiMutation("put", "/api/app/account/settings");

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
    <form className={styles.form} onSubmit={submit}>
      <Section title={ACCOUNT_TITLE}>
        <div className={styles.fields}>
          <Input
            id="account-name"
            label={NAME_LABEL}
            onChange={(event) => {
              setSettings({ ...settings, name: event.target.value });
            }}
            required
            value={settings.name}
          />
        </div>
      </Section>
      <Section title={REGION_TITLE}>
        <div className={styles.fields}>
          <Input
            id="timezone"
            label={TIMEZONE_LABEL}
            list="timezones"
            onChange={(event) => {
              setSettings({ ...settings, timezone: event.target.value });
            }}
            required
            value={settings.timezone}
          />
          <Select
            id="default-country"
            label={COUNTRY_LABEL}
            onChange={(event) => {
              setSettings({ ...settings, defaultCountry: event.target.value });
            }}
            options={COUNTRIES}
            value={settings.defaultCountry}
          />
        </div>
        <datalist id="timezones">
          {TIMEZONES.map((zone) => (
            <option key={zone} value={zone} />
          ))}
        </datalist>
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
