import { useState } from "react";

import type { InboundRule } from "@/api/generated/dashboard";
import { useApiMutation } from "@/api/queries";
import { Button } from "@/components/Button/Button";
import { FormModal } from "@/components/FormModal/FormModal";
import type { Notice, Result } from "@/types";

import { ruleUpdateOf } from "../rules";
import { InboundRuleActionChoice } from "./InboundRuleActionChoice";
import { InboundRuleCoreFields } from "./InboundRuleCoreFields";
import {
  EMPTY_INBOUND_DRAFT,
  draftOfInboundRule,
  inboundRuleRequestOf,
  isInboundRuleSaveable,
} from "./rules";

const ADD_LABEL = "ADD";
const CLOSE_LABEL = "CLOSE";
const TITLE = "Add Inbound Rule";

interface Props {
  onClose: () => void;
  onSaved: () => void;
  rule: InboundRule | undefined;
}

export function AddInboundRuleModal({ onClose, onSaved, rule }: Props) {
  const [draft, setDraft] = useState(
    rule === undefined ? EMPTY_INBOUND_DRAFT : draftOfInboundRule(rule),
  );
  const [notice, setNotice] = useState<Notice>();
  const create = useApiMutation("post", "/api/app/rules/inbound");
  const update = useApiMutation("put", "/api/app/rules/inbound/{ruleId}");
  const pending = create.isPending || update.isPending;

  const settle = (result: Result<InboundRule>) => {
    if (result.status === "ERROR") {
      setNotice({ message: result.message, tone: "error" });
      return;
    }
    onSaved();
  };

  const submit = () => {
    const input = inboundRuleRequestOf(draft);
    if (rule === undefined) {
      create.mutate({ body: input }, { onSuccess: settle });
      return;
    }
    update.mutate(ruleUpdateOf({ input, ruleId: rule.ruleId }), { onSuccess: settle });
  };

  const footer = (
    <>
      <Button onClick={onClose} variant="secondary">
        {CLOSE_LABEL}
      </Button>
      <Button disabled={pending || !isInboundRuleSaveable(draft)} type="submit">
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
      <InboundRuleCoreFields draft={draft} onChange={setDraft} />
      <InboundRuleActionChoice draft={draft} onChange={setDraft} />
    </FormModal>
  );
}
