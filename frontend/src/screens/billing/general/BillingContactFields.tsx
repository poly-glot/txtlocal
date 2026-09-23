import type { GeneralSettings } from "@/api/generated/dashboard";
import { Input } from "@/components/Input/Input";

import styles from "./BillingContactFields.module.css";

const EMAIL_LABEL = "Account Email";
const MOBILE_LABEL = "Account Mobile";
const NAME_LABEL = "Account Name";
const NAME_MAX_CHARS = 100;

interface Props {
  draft: GeneralSettings;
  onChange: (patch: Partial<GeneralSettings>) => void;
}

export function BillingContactFields({ draft, onChange }: Props) {
  return (
    <div className={styles.fields}>
      <Input
        id="general-name"
        label={NAME_LABEL}
        maxLength={NAME_MAX_CHARS}
        onChange={(event) => {
          onChange({ name: event.target.value });
        }}
        required
        value={draft.name}
      />
      <Input
        id="general-email"
        label={EMAIL_LABEL}
        onChange={(event) => {
          onChange({ email: event.target.value });
        }}
        required
        type="email"
        value={draft.email}
      />
      <Input
        id="general-mobile"
        label={MOBILE_LABEL}
        onChange={(event) => {
          onChange({ mobile: event.target.value || null });
        }}
        type="tel"
        value={draft.mobile ?? ""}
      />
    </div>
  );
}
