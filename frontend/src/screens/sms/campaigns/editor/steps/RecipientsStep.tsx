import { useApiQuery } from "@/api/queries";
import { Select } from "@/components/Select/Select";
import { dataOf } from "@/lib/format";

import { StepSection } from "./StepSection";
import { listSummary, sendableLists } from "./rules";

import styles from "./RecipientsStep.module.css";

const LIST_LABEL = "List";
const SELECT_LIST = "Select List";
const SUBTITLE = "Your Recipients";
const STEP = 1;
const TITLE = "To";

interface Props {
  listId: string;
  onChange: (listId: string) => void;
}

export function RecipientsStep({ listId, onChange }: Props) {
  const lists = useApiQuery("get", "/api/app/lists");
  const options = sendableLists(dataOf(lists.data, []));
  const chosen = options.find((list) => list.listId === listId);

  return (
    <StepSection complete={chosen !== undefined} step={STEP} subtitle={SUBTITLE} title={TITLE}>
      <Select
        id="campaign-list"
        label={LIST_LABEL}
        onChange={(event) => {
          onChange(event.target.value);
        }}
        options={[
          { label: SELECT_LIST, value: "" },
          ...options.map((list) => ({ label: list.name, value: list.listId })),
        ]}
        value={listId}
      />
      {chosen === undefined ? null : <p className={styles.summary}>{listSummary(chosen)}</p>}
    </StepSection>
  );
}
