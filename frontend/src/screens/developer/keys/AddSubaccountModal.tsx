import { useState } from "react";
import type { ChangeEvent, SubmitEvent } from "react";

import type { CreatedUser } from "@/api/generated/dashboard";
import { useApiMutation } from "@/api/queries";
import { Button } from "@/components/Button/Button";
import { Input } from "@/components/Input/Input";
import { Modal } from "@/components/Modal/Modal";
import { Toast } from "@/components/Toast/Toast";
import type { Notice } from "@/types";

import type { SubaccountDraft } from "./rules";
import { EMPTY_SUBACCOUNT, SUBACCOUNT_FIELDS, toNewSubaccount } from "./rules";

const ADD_LABEL = "ADD";
const CANCEL_LABEL = "Cancel";
const TITLE = "Add subaccount";
const TITLE_ID = "add-subaccount-title";

interface Props {
  onClose: () => void;
  onCreated: (created: CreatedUser) => void;
}

export function AddSubaccountModal({ onClose, onCreated }: Props) {
  const [draft, setDraft] = useState(EMPTY_SUBACCOUNT);
  const [notice, setNotice] = useState<Notice>();
  const create = useApiMutation("post", "/api/app/account/users");

  const update = (name: keyof SubaccountDraft) => (event: ChangeEvent<HTMLInputElement>) => {
    setDraft({ ...draft, [name]: event.target.value });
  };

  const submit = (event: SubmitEvent<HTMLFormElement>) => {
    event.preventDefault();
    create.mutate(
      { body: toNewSubaccount(draft) },
      {
        onSuccess: (result) => {
          if (result.status === "OK") {
            onCreated(result.data);
            return;
          }
          setNotice({ message: result.message, tone: "error" });
        },
      },
    );
  };

  return (
    <Modal labelledBy={TITLE_ID} onClose={onClose}>
      <form onSubmit={submit}>
        <Modal.Header>
          <Modal.Title id={TITLE_ID}>{TITLE}</Modal.Title>
        </Modal.Header>
        <Modal.Body>
          {SUBACCOUNT_FIELDS.map((field) => (
            <Input
              id={`subaccount-${field.name}`}
              key={field.name}
              label={field.label}
              maxLength={field.maxLength}
              onChange={update(field.name)}
              required={field.required}
              type={field.type}
              value={draft[field.name]}
            />
          ))}
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
          <Button disabled={create.isPending} type="submit">
            {ADD_LABEL}
          </Button>
        </Modal.Footer>
      </form>
    </Modal>
  );
}
