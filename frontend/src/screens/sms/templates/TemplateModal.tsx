import { useState } from "react";
import type { SubmitEvent } from "react";

import type { Template, TemplateRequest } from "@/api/generated/dashboard";
import { useApiMutation } from "@/api/queries";
import { Button } from "@/components/Button/Button";
import { Icon } from "@/components/Icon/Icon";
import { IconButton } from "@/components/IconButton/IconButton";
import { Input } from "@/components/Input/Input";
import { MessageBody } from "@/components/MessageBody/MessageBody";
import { Modal } from "@/components/Modal/Modal";
import { noticeOf } from "@/lib/notice";
import { segmentSummary, segmentsOf } from "@/rules/segments";
import type { Notice, Result } from "@/types";

import styles from "./TemplateModal.module.css";

const ADD_LABEL = "ADD";
const BODY_LABEL = "Body";
const CLOSE_ICON_LABEL = "Close";
const CLOSE_LABEL = "CLOSE";
const NAME_LABEL = "Template Name";
const NAME_MAX_CHARS = 100;
const SAVED_MSG = "New template has been saved.";
const TITLE = "SMS Template";
const TITLE_ID = "template-modal-title";

interface Props {
  onClose: () => void;
  onSaved: (notice: Notice) => void;
  template: Template | undefined;
}

export function TemplateModal({ onClose, onSaved, template }: Props) {
  const [body, setBody] = useState(template?.body ?? "");
  const [name, setName] = useState(template?.name ?? "");
  const create = useApiMutation("post", "/api/app/templates");
  const update = useApiMutation("put", "/api/app/templates/{templateId}");

  const saved = (result: Result<Template>) => {
    onSaved(noticeOf(result, SAVED_MSG));
  };

  const submit = (event: SubmitEvent<HTMLFormElement>) => {
    event.preventDefault();
    const input: TemplateRequest = { body, name };
    if (template === undefined) {
      create.mutate({ body: input }, { onSuccess: saved });
      return;
    }
    update.mutate(
      { body: input, params: { path: { templateId: template.templateId } } },
      { onSuccess: saved },
    );
  };

  return (
    <Modal labelledBy={TITLE_ID} onClose={onClose}>
      <form onSubmit={submit}>
        <Modal.Header>
          <div className={styles.heading}>
            <Modal.Title id={TITLE_ID}>{TITLE}</Modal.Title>
            <IconButton icon="close" label={CLOSE_ICON_LABEL} onClick={onClose} />
          </div>
        </Modal.Header>
        <Modal.Body>
          <Input
            id="template-name"
            label={NAME_LABEL}
            maxLength={NAME_MAX_CHARS}
            onChange={(event) => {
              setName(event.target.value);
            }}
            value={name}
          />
          <MessageBody id="template-body" label={BODY_LABEL} onChange={setBody} value={body}>
            {segmentSummary(segmentsOf(body))} <Icon name="info" size={14} />
          </MessageBody>
        </Modal.Body>
        <Modal.Footer>
          <Button onClick={onClose} variant="secondary">
            {CLOSE_LABEL}
          </Button>
          <Button
            disabled={body === "" || name === "" || create.isPending || update.isPending}
            type="submit"
          >
            {ADD_LABEL}
          </Button>
        </Modal.Footer>
      </form>
    </Modal>
  );
}
