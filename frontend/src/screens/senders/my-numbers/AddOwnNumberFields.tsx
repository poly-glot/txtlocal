import { Button } from "@/components/Button/Button";
import { Input } from "@/components/Input/Input";
import { Select } from "@/components/Select/Select";
import { COUNTRY_CODES } from "@/rules/countries";

import { countryOptions } from "../rules";
import type { OwnNumberDraft } from "./rules";
import { CODE_DIGITS, isDiallable } from "./rules";

import styles from "./AddOwnNumberFields.module.css";

const CODE_LABEL = "Verification Code";
const CODE_PLACEHOLDER = "Enter your 6-digit code";
const COUNTRY_LABEL = "Country";
const NICKNAME_HELPER = "Optional";
const NICKNAME_LABEL = "Nickname";
const NICKNAME_PLACEHOLDER = 'eg. "Sam\'s Phone"';
const NUMBER_HINT = "Standard SMS charges apply.";
const NUMBER_LABEL = "Your Own Number";
const NUMBER_PLACEHOLDER = "Enter your number";
const SEND_CODE_LABEL = "Send Code";

const COUNTRIES = countryOptions(COUNTRY_CODES);

interface Props {
  codeSent: boolean;
  draft: OwnNumberDraft;
  onChange: (draft: OwnNumberDraft) => void;
  onSendCode: () => void;
  sending: boolean;
}

export function AddOwnNumberFields({ codeSent, draft, onChange, onSendCode, sending }: Props) {
  return (
    <div className={styles.fields}>
      <Input
        helper={NICKNAME_HELPER}
        id="own-nickname"
        label={NICKNAME_LABEL}
        onChange={(event) => {
          onChange({ ...draft, nickname: event.target.value });
        }}
        placeholder={NICKNAME_PLACEHOLDER}
        value={draft.nickname}
      />
      <Select
        id="own-country"
        label={COUNTRY_LABEL}
        onChange={(event) => {
          onChange({ ...draft, country: event.target.value });
        }}
        options={COUNTRIES}
        value={draft.country}
      />
      <div className={styles.number}>
        <Input
          helper={NUMBER_HINT}
          id="own-number"
          label={NUMBER_LABEL}
          onChange={(event) => {
            onChange({ ...draft, number: event.target.value });
          }}
          placeholder={NUMBER_PLACEHOLDER}
          type="tel"
          value={draft.number}
        />
        <Button
          disabled={sending || !isDiallable(draft.number)}
          onClick={onSendCode}
          variant="secondary"
        >
          {SEND_CODE_LABEL}
        </Button>
      </div>
      <Input
        disabled={!codeSent}
        id="own-code"
        inputMode="numeric"
        label={CODE_LABEL}
        maxLength={CODE_DIGITS}
        onChange={(event) => {
          onChange({ ...draft, code: event.target.value });
        }}
        placeholder={CODE_PLACEHOLDER}
        value={draft.code}
      />
    </div>
  );
}
