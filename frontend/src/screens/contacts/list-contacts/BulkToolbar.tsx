import type { BulkRequest } from "@/api/generated/dashboard";
import { useApiMutation } from "@/api/queries";
import { Button } from "@/components/Button/Button";
import type { Notice } from "@/types";

import { actionNotice } from "./rules";

import styles from "./BulkToolbar.module.css";

const DELETE_LABEL = "Delete";
const OPT_OUT_LABEL = "Move to opt-out";

const selectedLabel = (count: number) => `${String(count)} selected`;

interface Props {
  listId: string;
  onDone: (notice: Notice) => void;
  selected: ReadonlySet<string>;
}

export function BulkToolbar({ listId, onDone, selected }: Props) {
  const bulk = useApiMutation("post", "/api/app/lists/{listId}/contacts/bulk");

  const act = (action: BulkRequest["action"]) => {
    bulk.mutate(
      { body: { action, contactIds: [...selected] }, params: { path: { listId } } },
      {
        onSuccess: (result) => {
          onDone(actionNotice(result));
        },
      },
    );
  };

  return (
    <div className={styles.toolbar}>
      <p className={styles.count}>{selectedLabel(selected.size)}</p>
      <Button
        onClick={() => {
          act("DELETE");
        }}
        variant="danger"
      >
        {DELETE_LABEL}
      </Button>
      <Button
        onClick={() => {
          act("OPT_OUT");
        }}
        variant="secondary"
      >
        {OPT_OUT_LABEL}
      </Button>
    </div>
  );
}
