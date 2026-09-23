import { Input } from "@/components/Input/Input";
import { Select } from "@/components/Select/Select";
import type { Option } from "@/components/Select/Select";

import type { AlphaTagDraft } from "./rules";
import { ALPHA_TAG_MAX, USE_CASE_OPTIONS, isUseCase } from "./rules";

import styles from "./RegisterAlphaTagFields.module.css";

const COUNTRY_LABEL = "Sending to";
const TAG_HINT = "3-11 characters. Numbers, letters, pluses only.";
const TAG_LABEL = "Alpha Tag";
const TAG_PLACEHOLDER = "eg. Your business or product name";
const USE_CASE_LABEL = "Your Use Case";

interface Props {
  countries: readonly Option[];
  draft: AlphaTagDraft;
  onChange: (draft: AlphaTagDraft) => void;
}

export function RegisterAlphaTagFields({ countries, draft, onChange }: Props) {
  return (
    <div className={styles.fields}>
      <Select
        id="alpha-country"
        label={COUNTRY_LABEL}
        onChange={(event) => {
          onChange({ ...draft, country: event.target.value });
        }}
        options={countries}
        value={draft.country}
      />
      <Input
        helper={TAG_HINT}
        id="alpha-tag"
        label={TAG_LABEL}
        maxLength={ALPHA_TAG_MAX}
        onChange={(event) => {
          onChange({ ...draft, tag: event.target.value });
        }}
        placeholder={TAG_PLACEHOLDER}
        value={draft.tag}
      />
      <Select
        id="alpha-use-case"
        label={USE_CASE_LABEL}
        onChange={(event) => {
          const { value } = event.target;
          if (isUseCase(value)) {
            onChange({ ...draft, useCase: value });
          }
        }}
        options={USE_CASE_OPTIONS}
        value={draft.useCase}
      />
    </div>
  );
}
