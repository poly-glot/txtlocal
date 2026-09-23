import { useState } from "react";

import type { InboundRule } from "@/api/generated/dashboard";
import { useApiMutation } from "@/api/queries";
import { Button } from "@/components/Button/Button";
import { ConfirmDeleteModal } from "@/components/ConfirmDeleteModal/ConfirmDeleteModal";
import { PagedRows } from "@/components/PagedRows/PagedRows";
import { Panel } from "@/components/Panel/Panel";
import { Toast } from "@/components/Toast/Toast";
import { refusalNotice } from "@/lib/notice";
import type { Notice, Result } from "@/types";

import { ruleUpdateOf } from "../rules";
import { AddInboundRuleModal } from "./AddInboundRuleModal";
import { InboundRulesTable } from "./InboundRulesTable";
import { toggledInboundRule } from "./rules";

import styles from "./InboundRulesPanel.module.css";

const ADD_LABEL = "ADD NEW RULE";
const DELETE_TITLE = "Delete inbound rule";
const DELETED_MSG = "Inbound rule deleted.";
const SAVED_MSG = "Inbound rule saved.";

const deleteQuestion = (name: string) =>
  `Delete the inbound rule "${name}"? This cannot be undone.`;

interface Props {
  rules: readonly InboundRule[];
  title: string;
}

export function InboundRulesPanel({ rules, title }: Props) {
  const [deleting, setDeleting] = useState<InboundRule>();
  const [editor, setEditor] = useState<{ rule: InboundRule | undefined }>();
  const [notice, setNotice] = useState<Notice>();
  const remove = useApiMutation("delete", "/api/app/rules/inbound/{ruleId}");
  const update = useApiMutation("put", "/api/app/rules/inbound/{ruleId}");

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
      <div className={styles.body}>
        <Toast
          notice={notice}
          onDismiss={() => {
            setNotice(undefined);
          }}
        />
        <PagedRows rows={rules}>
          {(page) => (
            <InboundRulesTable
              onDelete={setDeleting}
              onEdit={(rule) => {
                setEditor({ rule });
              }}
              onToggle={(rule) => {
                update.mutate(ruleUpdateOf(toggledInboundRule(rule)), { onSuccess: showRefusal });
              }}
              rows={page}
            />
          )}
        </PagedRows>
      </div>
      {editor === undefined ? null : (
        <AddInboundRuleModal
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
