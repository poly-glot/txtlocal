import { useState } from "react";

import { useApiMutation } from "@/api/queries";
import { Button } from "@/components/Button/Button";
import { FormModal } from "@/components/FormModal/FormModal";
import { RowAction } from "@/components/RowAction/RowAction";
import type { Notice } from "@/types";

import { WebsiteDomainRow } from "./WebsiteDomainRow";
import {
  MAX_WEBSITES_PER_SUBMISSION,
  hasRegisterableDomain,
  websitesRequestOf,
  withDomainAt,
  withDomainRow,
  withoutDomainRow,
} from "./rules";

import styles from "./RegisterWebsiteModal.module.css";

const ADD_ANOTHER_LABEL = "Add another website +";
const CLOSE_LABEL = "Close";
const COPY = "Registering websites keeps customers safe, reduces spam and speeds up delivery.";
const HINT = "You can register up to 3 different websites at once.";
const REGISTER_LABEL = "Register";
const SUPPORT_TEXT = "Having an issue? Contact Support";
const TITLE = "Register a website";

interface Props {
  onClose: () => void;
  onRegistered: () => void;
}

export function RegisterWebsiteModal({ onClose, onRegistered }: Props) {
  const [domains, setDomains] = useState<string[]>([""]);
  const [notice, setNotice] = useState<Notice>();
  const register = useApiMutation("post", "/api/app/websites");
  const canRemove = domains.length > 1;

  const submit = () => {
    register.mutate(
      { body: websitesRequestOf(domains) },
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

  const footer = (
    <>
      <Button onClick={onClose} variant="secondary">
        {CLOSE_LABEL}
      </Button>
      <Button disabled={register.isPending || !hasRegisterableDomain(domains)} type="submit">
        {REGISTER_LABEL}
      </Button>
    </>
  );

  return (
    <FormModal
      footer={footer}
      notice={notice}
      onClose={onClose}
      onDismissNotice={() => {
        setNotice(undefined);
      }}
      onSubmit={submit}
      title={TITLE}
    >
      <p className={styles.copy}>{COPY}</p>
      {domains.map((domain, index) => (
        <WebsiteDomainRow
          domain={domain}
          hint={index === 0 ? HINT : undefined}
          key={String(index)}
          onChange={(value) => {
            setDomains(withDomainAt(domains, index, value));
          }}
          onRemove={
            canRemove
              ? () => {
                  setDomains(withoutDomainRow(domains, index));
                }
              : undefined
          }
        />
      ))}
      {domains.length < MAX_WEBSITES_PER_SUBMISSION ? (
        <span className={styles.addRow}>
          <RowAction
            onClick={() => {
              setDomains(withDomainRow(domains));
            }}
          >
            {ADD_ANOTHER_LABEL}
          </RowAction>
        </span>
      ) : null}
      <p className={styles.support}>{SUPPORT_TEXT}</p>
    </FormModal>
  );
}
