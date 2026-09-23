import { useState } from "react";

import type { DeliveryReportRuleView } from "@/api/generated/dashboard";
import { useApiMutation } from "@/api/queries";
import { Button } from "@/components/Button/Button";
import { FormModal } from "@/components/FormModal/FormModal";
import type { Notice } from "@/types";

import { ruleUpdateOf } from "../rules";
import { DeliveryRuleFields } from "./DeliveryRuleFields";
import { DeliverySecretModal } from "./DeliverySecretModal";
import {
  EMPTY_DELIVERY_DRAFT,
  deliveryRuleRequestOf,
  draftOfDeliveryRule,
  isDeliveryRuleSaveable,
} from "./rules";

const ADD_LABEL = "ADD";
const CLOSE_LABEL = "CLOSE";
const TITLE = "Add Delivery Report Rule";

interface Props {
  onClose: () => void;
  onSaved: () => void;
  rule: DeliveryReportRuleView | undefined;
}

export function AddDeliveryRuleModal({ onClose, onSaved, rule }: Props) {
  const [draft, setDraft] = useState(
    rule === undefined ? EMPTY_DELIVERY_DRAFT : draftOfDeliveryRule(rule),
  );
  const [notice, setNotice] = useState<Notice>();
  const [secret, setSecret] = useState<string>();
  const create = useApiMutation("post", "/api/app/rules/delivery");
  const update = useApiMutation("put", "/api/app/rules/delivery/{ruleId}");
  const pending = create.isPending || update.isPending;

  if (secret !== undefined) {
    return <DeliverySecretModal onDone={onSaved} secret={secret} />;
  }

  const submit = () => {
    const input = deliveryRuleRequestOf(draft);

    if (rule === undefined) {
      create.mutate(
        { body: input },
        {
          onSuccess: (result) => {
            if (result.status === "ERROR") {
              setNotice({ message: result.message, tone: "error" });
              return;
            }
            setSecret(result.data.secret);
          },
        },
      );
      return;
    }

    update.mutate(ruleUpdateOf({ input, ruleId: rule.ruleId }), {
      onSuccess: (result) => {
        if (result.status === "ERROR") {
          setNotice({ message: result.message, tone: "error" });
          return;
        }
        onSaved();
      },
    });
  };

  const footer = (
    <>
      <Button onClick={onClose} variant="secondary">
        {CLOSE_LABEL}
      </Button>
      <Button disabled={pending || !isDeliveryRuleSaveable(draft)} type="submit">
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
      <DeliveryRuleFields draft={draft} onChange={setDraft} />
    </FormModal>
  );
}
