import type { SenderView } from "@/api/generated/dashboard";
import { Input } from "@/components/Input/Input";
import { Select } from "@/components/Select/Select";

import type { EmailSenderDraft, SubaccountOption } from "./rules";
import { readySenderOptions, subaccountOptions } from "./rules";

import styles from "./AllowedAddressFields.module.css";

const CHOOSE_SENDER_LABEL = "Choose a sender";
const CHOOSE_SUBACCOUNT_LABEL = "Choose a subaccount";
const EMAIL_LABEL = "Email Address";
const SENDER_LABEL = "Sender";
const SUBACCOUNT_LABEL = "Subaccount";

interface Props {
  draft: EmailSenderDraft;
  onChange: (draft: EmailSenderDraft) => void;
  senders: readonly SenderView[];
  subaccounts: readonly SubaccountOption[];
}

export function AllowedAddressFields({ draft, onChange, senders, subaccounts }: Props) {
  return (
    <div className={styles.grid}>
      <Select
        id="allowed-address-subaccount"
        label={SUBACCOUNT_LABEL}
        onChange={(event) => {
          onChange({ ...draft, userId: event.target.value });
        }}
        options={[{ label: CHOOSE_SUBACCOUNT_LABEL, value: "" }, ...subaccountOptions(subaccounts)]}
        value={draft.userId}
      />
      <Select
        id="allowed-address-sender"
        label={SENDER_LABEL}
        onChange={(event) => {
          onChange({ ...draft, senderId: event.target.value });
        }}
        options={[{ label: CHOOSE_SENDER_LABEL, value: "" }, ...readySenderOptions(senders)]}
        value={draft.senderId}
      />
      <div className={styles.wide}>
        <Input
          id="allowed-address-email"
          label={EMAIL_LABEL}
          onChange={(event) => {
            onChange({ ...draft, email: event.target.value });
          }}
          type="email"
          value={draft.email}
        />
      </div>
    </div>
  );
}
