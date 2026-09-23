import { Input } from "@/components/Input/Input";
import { Select } from "@/components/Select/Select";

import type { DeliveryRuleDraft } from "./rules";
import { DELIVERY_EVENT_OPTIONS, isDeliveryEvents } from "./rules";

import styles from "./DeliveryRuleFields.module.css";

const EVENTS_LABEL = "Events";
const NAME_LABEL = "Rule Name";
const URL_HELPER = "Must start with https://";
const URL_LABEL = "URL";

interface Props {
  draft: DeliveryRuleDraft;
  onChange: (draft: DeliveryRuleDraft) => void;
}

export function DeliveryRuleFields({ draft, onChange }: Props) {
  return (
    <div className={styles.grid}>
      <Input
        id="delivery-rule-name"
        label={NAME_LABEL}
        onChange={(event) => {
          onChange({ ...draft, name: event.target.value });
        }}
        value={draft.name}
      />
      <Select
        id="delivery-rule-events"
        label={EVENTS_LABEL}
        onChange={(event) => {
          if (isDeliveryEvents(event.target.value)) {
            onChange({ ...draft, events: event.target.value });
          }
        }}
        options={DELIVERY_EVENT_OPTIONS}
        value={draft.events}
      />
      <div className={styles.wide}>
        <Input
          helper={URL_HELPER}
          id="delivery-rule-url"
          label={URL_LABEL}
          onChange={(event) => {
            onChange({ ...draft, url: event.target.value });
          }}
          type="url"
          value={draft.url}
        />
      </div>
    </div>
  );
}
