import { Input } from "@/components/Input/Input";
import { Select } from "@/components/Select/Select";
import type { Option } from "@/components/Select/Select";
import { segmentSummary, segmentsOf } from "@/rules/segments";

import type { ActionField, ActionFieldKind } from "./rules";

import styles from "./InboundRuleActionField.module.css";

const CHOOSE_LIST_LABEL = "Choose a list";

const INPUT_TYPE: Record<ActionFieldKind, string> = {
  email: "email",
  list: "text",
  text: "text",
  textarea: "text",
  url: "url",
};

interface Props {
  field: ActionField;
  listOptions: readonly Option[];
  onChange: (value: string) => void;
  value: string;
}

export function InboundRuleActionField({ field, listOptions, onChange, value }: Props) {
  const id = `inbound-rule-${field.target}`;
  const helperProps = field.helper === undefined ? {} : { helper: field.helper };

  if (field.kind === "list") {
    return (
      <Select
        id={id}
        label={field.label}
        onChange={(event) => {
          onChange(event.target.value);
        }}
        options={[{ label: CHOOSE_LIST_LABEL, value: "" }, ...listOptions]}
        value={value}
      />
    );
  }

  if (field.kind === "textarea") {
    return (
      <div className={styles.field}>
        <label className={styles.label} htmlFor={id}>
          {field.label}
        </label>
        <textarea
          className={styles.textarea}
          id={id}
          onChange={(event) => {
            onChange(event.target.value);
          }}
          rows={4}
          value={value}
        />
        <p className={styles.counter}>{segmentSummary(segmentsOf(value))}</p>
      </div>
    );
  }

  return (
    <Input
      {...helperProps}
      id={id}
      label={field.label}
      onChange={(event) => {
        onChange(event.target.value);
      }}
      type={INPUT_TYPE[field.kind]}
      value={value}
    />
  );
}
