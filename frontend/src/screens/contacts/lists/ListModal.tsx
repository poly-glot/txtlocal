import { useState } from "react";
import type { SubmitEvent } from "react";

import type { ContactList } from "@/api/generated/dashboard";
import { useApiMutation } from "@/api/queries";
import { Button } from "@/components/Button/Button";
import { Input } from "@/components/Input/Input";
import { Modal } from "@/components/Modal/Modal";
import { Toast } from "@/components/Toast/Toast";
import { refusalNotice } from "@/lib/notice";
import type { Notice, Result } from "@/types";

import type { ListDraft } from "./rules";
import { MAX_LIST_NAME_CHARS } from "./rules";

const CANCEL_LABEL = "Cancel";
const CREATE_LABEL = "ADD";
const CREATE_TITLE = "New list";
const NAME_LABEL = "Name";
const RENAME_TITLE = "Rename list";
const SAVE_LABEL = "SAVE";
const TITLE_ID = "list-modal-title";

interface Props {
  draft: ListDraft;
  onClose: () => void;
  onSaved: (list: ContactList) => void;
}

export function ListModal({ draft, onClose, onSaved }: Props) {
  const [name, setName] = useState(draft.name);
  const [notice, setNotice] = useState<Notice>();
  const create = useApiMutation("post", "/api/app/lists");
  const rename = useApiMutation("patch", "/api/app/lists/{listId}");
  const creating = draft.listId === null;

  const submit = (event: SubmitEvent<HTMLFormElement>) => {
    event.preventDefault();
    const saved = {
      onSuccess: (result: Result<ContactList>) => {
        if (result.status === "OK") {
          onSaved(result.data);
          return;
        }
        setNotice(refusalNotice(result));
      },
    };

    if (draft.listId === null) {
      create.mutate({ body: { name } }, saved);
    } else {
      rename.mutate({ body: { name }, params: { path: { listId: draft.listId } } }, saved);
    }
  };

  return (
    <Modal labelledBy={TITLE_ID} onClose={onClose}>
      <form onSubmit={submit}>
        <Modal.Header>
          <Modal.Title id={TITLE_ID}>{creating ? CREATE_TITLE : RENAME_TITLE}</Modal.Title>
        </Modal.Header>
        <Modal.Body>
          <Input
            id="list-name"
            label={NAME_LABEL}
            maxLength={MAX_LIST_NAME_CHARS}
            onChange={(event) => {
              setName(event.target.value);
            }}
            required
            value={name}
          />
          <Toast
            notice={notice}
            onDismiss={() => {
              setNotice(undefined);
            }}
          />
        </Modal.Body>
        <Modal.Footer>
          <Button onClick={onClose} variant="secondary">
            {CANCEL_LABEL}
          </Button>
          <Button disabled={create.isPending || rename.isPending} type="submit">
            {creating ? CREATE_LABEL : SAVE_LABEL}
          </Button>
        </Modal.Footer>
      </form>
    </Modal>
  );
}
