import { useState } from "react";

import type { DeliveryReportRuleView } from "@/api/generated/dashboard";
import { useApiMutation } from "@/api/queries";
import { Button } from "@/components/Button/Button";
import { ConfirmDeleteModal } from "@/components/ConfirmDeleteModal/ConfirmDeleteModal";
import { Panel } from "@/components/Panel/Panel";
import { Toast } from "@/components/Toast/Toast";
import { refusalNotice } from "@/lib/notice";
import type { Notice, Result } from "@/types";

import { ruleUpdateOf } from "../rules";
import { AddDeliveryRuleModal } from "./AddDeliveryRuleModal";
import { DeliveryRulesTable } from "./DeliveryRulesTable";
import { toggledDeliveryRule } from "./rules";

const ADD_LABEL = "ADD NEW RULE";
const DELETE_TITLE = "Delete delivery report rule";
const DELETED_MSG = "Delivery report rule deleted.";
const SAVED_MSG = "Delivery report rule saved.";

const deleteQuestion = (name: string) =>
  `Delete the delivery report rule "${name}"? This cannot be undone.`;

interface Props {
  rules: readonly DeliveryReportRuleView[];
  title: string;
}

export function DeliveryRulesPanel({ rules, title }: Props) {
  const [deleting, setDeleting] = useState<DeliveryReportRuleView>();
  const [editor, setEditor] = useState<{ rule: DeliveryReportRuleView | undefined }>();
  const [notice, setNotice] = useState<Notice>();
  const remove = useApiMutation("delete", "/api/app/rules/delivery/{ruleId}");
  const update = useApiMutation("put", "/api/app/rules/delivery/{ruleId}");

  const showRefusal = (result: Result<unknown>) => {
    setNotice((current) => refusalNotice(result) ?? current);
  };

  const addRule = (
    <Button
      onClick={() => {
        setEditor({ rule: undefined });
      }}
    >
      {ADD_LABEL}
    </Button>
  );

  return (
    <Panel actions={addRule} title={title}>
      <Toast
        notice={notice}
        onDismiss={() => {
          setNotice(undefined);
        }}
      />
      <DeliveryRulesTable
        onDelete={setDeleting}
        onEdit={(rule) => {
          setEditor({ rule });
        }}
        onToggle={(rule) => {
          update.mutate(ruleUpdateOf(toggledDeliveryRule(rule)), { onSuccess: showRefusal });
        }}
        rows={rules}
      />
      {editor === undefined ? null : (
        <AddDeliveryRuleModal
          onClose={() => {
            setEditor(undefined);
          }}
          onSaved={() => {
            setEditor(undefined);
            setNotice({ message: SAVED_MSG, tone: "success" });
          }}
          rule={editor.rule}
        />
      )}
      {deleting === undefined ? null : (
        <ConfirmDeleteModal
          onCancel={() => {
            setDeleting(undefined);
          }}
          onDeleted={() => {
            setDeleting(undefined);
            setNotice({ message: DELETED_MSG, tone: "success" });
          }}
          question={deleteQuestion(deleting.name)}
          pending={remove.isPending}
          remove={(removal) => {
            remove.mutate({ params: { path: { ruleId: deleting.ruleId } } }, removal);
          }}
          title={DELETE_TITLE}
        />
      )}
    </Panel>
  );
}
