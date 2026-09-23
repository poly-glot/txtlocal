import { useState } from "react";
import type { SubmitEvent } from "react";

import { useApiMutation } from "@/api/queries";
import { Button } from "@/components/Button/Button";
import { Modal } from "@/components/Modal/Modal";
import type { Option } from "@/components/Select/Select";
import { Toast } from "@/components/Toast/Toast";
import type { Notice } from "@/types";

import { RegisterAlphaTagFields } from "./RegisterAlphaTagFields";
import type { AlphaTagDraft } from "./rules";
import { isValidAlphaTag } from "./rules";

import styles from "./RegisterAlphaTagModal.module.css";

const CLOSE_LABEL = "Close";
const COPY =
  "You must register your alpha tag in order to start sending. Customers cannot reply to alpha tags. Some countries may need additional registration or block alpha tags.";
const REGISTER_LABEL = "Register Alpha Tag";
const SUPPORT_TEXT = "Having an issue? Contact Support";
const TITLE = "Register an alpha tag";
const TITLE_ID = "register-alpha-tag-title";

interface Props {
  countries: readonly Option[];
  initial: AlphaTagDraft;
  onClose: () => void;
  onRegistered: () => void;
}

export function RegisterAlphaTagModal({ countries, initial, onClose, onRegistered }: Props) {
  const [draft, setDraft] = useState(initial);
  const [notice, setNotice] = useState<Notice>();
  const register = useApiMutation("post", "/api/app/senders/alpha");

  const submit = (event: SubmitEvent<HTMLFormElement>) => {
    event.preventDefault();
    register.mutate(
      { body: draft },
      {
        onSuccess: (result) => {
          if (result.status === "ERROR") {
            setNotice({ message: result.message, tone: "error" });
            return;
          }
          onRegistered();
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
          <p className={styles.copy}>{COPY}</p>
          <RegisterAlphaTagFields countries={countries} draft={draft} onChange={setDraft} />
          <Toast
            notice={notice}
            onDismiss={() => {
              setNotice(undefined);
            }}
          />
          <p className={styles.support}>{SUPPORT_TEXT}</p>
        </Modal.Body>
        <Modal.Footer>
          <Button onClick={onClose} variant="secondary">
            {CLOSE_LABEL}
          </Button>
          <Button disabled={register.isPending || !isValidAlphaTag(draft.tag)} type="submit">
            {REGISTER_LABEL}
          </Button>
        </Modal.Footer>
      </form>
    </Modal>
  );
}
