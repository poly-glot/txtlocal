import { useApiQuery } from "@/api/queries";
import { Input } from "@/components/Input/Input";
import { Select } from "@/components/Select/Select";
import { dataOf } from "@/lib/format";
import { EMPTY_SENDERS_VIEW } from "@/rules/senders";

import type { InboundRuleDraft } from "./rules";
import { MATCH_KIND_OPTIONS, dedicatedNumbers, numberOptions } from "./rules";

import styles from "./InboundRuleCoreFields.module.css";

const ANY_LABEL = "Any";
const KEYWORD_LABEL = "Keyword";
const MATCH_HELPER = "A match on the incoming SMS";
const MATCH_LABEL = "Match For";
const NAME_HELPER = "This is for your reference only";
const NAME_LABEL = "Rule Name";
const NUMBER_HELPER = "A txtlocal number you've purchased (optional)";
const NUMBER_LABEL = "Dedicated Number";

interface Props {
  draft: InboundRuleDraft;
  onChange: (draft: InboundRuleDraft) => void;
}

export function InboundRuleCoreFields({ draft, onChange }: Props) {
  const senders = useApiQuery("get", "/api/app/senders");
  const numbers = dedicatedNumbers(dataOf(senders.data, EMPTY_SENDERS_VIEW));

  return (
    <div className={styles.grid}>
      <Input
        helper={NAME_HELPER}
        id="inbound-rule-name"
        label={NAME_LABEL}
        onChange={(event) => {
          onChange({ ...draft, name: event.target.value });
        }}
        value={draft.name}
      />
      <Select
        helper={NUMBER_HELPER}
        id="inbound-rule-number"
        label={NUMBER_LABEL}
        onChange={(event) => {
          onChange({ ...draft, number: event.target.value });
        }}
        options={[{ label: ANY_LABEL, value: "" }, ...numberOptions(numbers)]}
        value={draft.number}
      />
      <Select
        helper={MATCH_HELPER}
        id="inbound-rule-match-kind"
        label={MATCH_LABEL}
        onChange={(event) => {
          onChange({ ...draft, matchKind: event.target.value === "KEYWORD" ? "KEYWORD" : "ANY" });
        }}
        options={MATCH_KIND_OPTIONS}
        value={draft.matchKind}
      />
      {draft.matchKind === "KEYWORD" ? (
        <Input
          id="inbound-rule-keyword"
          label={KEYWORD_LABEL}
          onChange={(event) => {
            onChange({ ...draft, keyword: event.target.value });
          }}
          value={draft.keyword}
        />
      ) : null}
    </div>
  );
}
