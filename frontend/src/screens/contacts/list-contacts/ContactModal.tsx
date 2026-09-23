import { useState } from "react";
import type { SubmitEvent } from "react";

import type { Contact } from "@/api/generated/dashboard";
import { useApiMutation } from "@/api/queries";
import { Button } from "@/components/Button/Button";
import { Input } from "@/components/Input/Input";
import { Modal } from "@/components/Modal/Modal";
import { Toast } from "@/components/Toast/Toast";
import { refusalNotice } from "@/lib/notice";
import type { Notice, Result } from "@/types";

import type { ContactEdit } from "./rules";
import { CONTACT_FIELDS } from "./rules";

import styles from "./ContactModal.module.css";

const ADD_LABEL = "ADD";
const ADD_TITLE = "Add contact";
const CANCEL_LABEL = "Cancel";
const EDIT_TITLE = "Edit contact";
const SAVE_LABEL = "SAVE";
const TITLE_ID = "contact-modal-title";

interface Props {
  edit: ContactEdit;
  listId: string;
  onClose: () => void;
}

export function ContactModal({ edit, listId, onClose }: Props) {
  const [input, setInput] = useState(edit.input);
  const [notice, setNotice] = useState<Notice>();
  const add = useApiMutation("post", "/api/app/lists/{listId}/contacts");
  const update = useApiMutation("patch", "/api/app/lists/{listId}/contacts/{contactId}");
  const adding = edit.contactId === null;

  const submit = (event: SubmitEvent<HTMLFormElement>) => {
    event.preventDefault();
    const saved = {
      onSuccess: (result: Result<Contact>) => {
        if (result.status === "OK") {
          onClose();
          return;
        }
        setNotice(refusalNotice(result));
      },
    };

    if (edit.contactId === null) {
      add.mutate({ body: input, params: { path: { listId } } }, saved);
    } else {
      update.mutate(
        { body: input, params: { path: { contactId: edit.contactId, listId } } },
        saved,
      );
    }
  };

  return (
    <Modal labelledBy={TITLE_ID} onClose={onClose}>
      <form onSubmit={submit}>
        <Modal.Header>
          <Modal.Title id={TITLE_ID}>{adding ? ADD_TITLE : EDIT_TITLE}</Modal.Title>
        </Modal.Header>
        <Modal.Body>
          <div className={styles.grid}>
            {CONTACT_FIELDS.map((field) => (
              <Input
                id={`contact-${field.name}`}
                key={field.name}
                label={field.label}
                maxLength={field.maxLength}
                onChange={(event) => {
                  setInput({ ...input, [field.name]: event.target.value });
                }}
                required={field.required}
                type={field.type}
                value={input[field.name]}
              />
            ))}
          </div>
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
          <Button disabled={add.isPending || update.isPending} type="submit">
            {adding ? ADD_LABEL : SAVE_LABEL}
          </Button>
        </Modal.Footer>
      </form>
    </Modal>
  );
}
