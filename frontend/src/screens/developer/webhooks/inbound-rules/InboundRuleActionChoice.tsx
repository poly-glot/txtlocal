import { useApiQuery } from "@/api/queries";
import { Select } from "@/components/Select/Select";
import { dataOf } from "@/lib/format";

import { InboundRuleActionField } from "./InboundRuleActionField";
import type { InboundRuleDraft } from "./rules";
import {
  ACTION_OPTIONS,
  actionFieldFor,
  actionFieldValue,
  isRuleAction,
  listOptions,
  withActionValue,
} from "./rules";

import styles from "./InboundRuleActionChoice.module.css";

const ACTION_LABEL = "Action";
const PROMPT = "If there's a match as specified above choose the action to run:";

interface Props {
  draft: InboundRuleDraft;
  onChange: (draft: InboundRuleDraft) => void;
}

export function InboundRuleActionChoice({ draft, onChange }: Props) {
  const lists = useApiQuery("get", "/api/app/lists");
  const field = actionFieldFor(draft.action);

  return (
    <>
      <p className={styles.prompt}>{PROMPT}</p>
      <div className={styles.grid}>
        <Select
          id="inbound-rule-action"
          label={ACTION_LABEL}
          onChange={(event) => {
            if (isRuleAction(event.target.value)) {
              onChange({ ...draft, action: event.target.value });
            }
          }}
          options={ACTION_OPTIONS}
          value={draft.action}
        />
        {field === null ? null : (
          <InboundRuleActionField
            field={field}
            listOptions={listOptions(dataOf(lists.data, []))}
            onChange={(value) => {
              onChange(withActionValue(draft, field, value));
            }}
            value={actionFieldValue(draft, field)}
          />
        )}
      </div>
    </>
  );
}
