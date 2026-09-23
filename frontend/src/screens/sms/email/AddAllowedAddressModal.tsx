import { useState } from "react";

import type { SenderView } from "@/api/generated/dashboard";
import { useApiMutation } from "@/api/queries";
import { Button } from "@/components/Button/Button";
import { FormModal } from "@/components/FormModal/FormModal";
import type { Notice } from "@/types";

import { AllowedAddressFields } from "./AllowedAddressFields";
import type { SubaccountOption } from "./rules";
import { EMPTY_EMAIL_SENDER_DRAFT, emailSenderRequestOf, isEmailSenderSaveable } from "./rules";

const ADD_LABEL = "ADD";
const CLOSE_LABEL = "Close";
const TITLE = "Add allowed address";

interface Props {
  onClose: () => void;
  onSaved: () => void;
  senders: readonly SenderView[];
  subaccounts: readonly SubaccountOption[];
}

export function AddAllowedAddressModal({ onClose, onSaved, senders, subaccounts }: Props) {
  const [draft, setDraft] = useState(EMPTY_EMAIL_SENDER_DRAFT);
  const [notice, setNotice] = useState<Notice>();
  const add = useApiMutation("post", "/api/app/email-senders");

  const submit = () => {
    add.mutate(
      { body: emailSenderRequestOf(draft) },
      {
        onSuccess: (result) => {
          if (result.status === "ERROR") {
            setNotice({ message: result.message, tone: "error" });
            return;
          }
          onSaved();
        },
      },
    );
  };

  const footer = (
    <>
      <Button onClick={onClose} variant="secondary">
        {CLOSE_LABEL}
      </Button>
      <Button disabled={add.isPending || !isEmailSenderSaveable(draft)} type="submit">
        {ADD_LABEL}
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
      <AllowedAddressFields
        draft={draft}
        onChange={setDraft}
        senders={senders}
        subaccounts={subaccounts}
      />
    </FormModal>
  );
}
