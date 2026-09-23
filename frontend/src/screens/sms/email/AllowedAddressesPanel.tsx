import { useState } from "react";

import type { EmailSender, SendersView } from "@/api/generated/dashboard";
import { useApiMutation } from "@/api/queries";
import { Button } from "@/components/Button/Button";
import { ConfirmDeleteModal } from "@/components/ConfirmDeleteModal/ConfirmDeleteModal";
import { PagedRows } from "@/components/PagedRows/PagedRows";
import { Panel } from "@/components/Panel/Panel";
import { Toast } from "@/components/Toast/Toast";
import type { Notice } from "@/types";

import { AddAllowedAddressModal } from "./AddAllowedAddressModal";
import { AllowedAddressesTable } from "./AllowedAddressesTable";
import type { SubaccountOption } from "./rules";
import { readySenders } from "./rules";

import styles from "./AllowedAddressesPanel.module.css";

const ADD_LABEL = "ADD";
const DELETE_TITLE = "Remove allowed address";
const DELETED_MSG = "Allowed address removed.";
const SAVED_MSG = "Allowed address added.";
const SHARED_NOTICE = "Allowed email address settings apply to every channel";

const deleteQuestion = (email: string) => `Remove ${email} from your allowed addresses?`;

interface Props {
  rows: readonly EmailSender[];
  senders: SendersView;
  subaccounts: readonly SubaccountOption[];
  title: string;
}

export function AllowedAddressesPanel({ rows, senders, subaccounts, title }: Props) {
  const [adding, setAdding] = useState(false);
  const [deleting, setDeleting] = useState<EmailSender>();
  const [notice, setNotice] = useState<Notice>();
  const remove = useApiMutation("delete", "/api/app/email-senders/{id}");

  const addAddress = (
    <Button
      onClick={() => {
        setAdding(true);
      }}
    >
      {ADD_LABEL}
    </Button>
  );

  return (
    <Panel actions={addAddress} title={title}>
      <div className={styles.body}>
        <p className={styles.notice}>{SHARED_NOTICE}</p>
        <Toast
          notice={notice}
          onDismiss={() => {
            setNotice(undefined);
          }}
        />
        <PagedRows rows={rows}>
          {(page) => (
            <AllowedAddressesTable
              onRemove={setDeleting}
              rows={page}
              senders={senders}
              subaccounts={subaccounts}
            />
          )}
        </PagedRows>
      </div>
      {adding ? (
        <AddAllowedAddressModal
          onClose={() => {
            setAdding(false);
          }}
          onSaved={() => {
            setAdding(false);
            setNotice({ message: SAVED_MSG, tone: "success" });
          }}
          senders={readySenders(senders)}
          subaccounts={subaccounts}
        />
      ) : null}
      {deleting === undefined ? null : (
        <ConfirmDeleteModal
          onCancel={() => {
            setDeleting(undefined);
          }}
          onDeleted={() => {
            setDeleting(undefined);
            setNotice({ message: DELETED_MSG, tone: "success" });
          }}
          question={deleteQuestion(deleting.email)}
          pending={remove.isPending}
          remove={(removal) => {
            remove.mutate({ params: { path: { id: deleting.email } } }, removal);
          }}
          title={DELETE_TITLE}
        />
      )}
    </Panel>
  );
}
