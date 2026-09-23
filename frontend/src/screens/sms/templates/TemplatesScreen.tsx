import { useState } from "react";

import type { Template } from "@/api/generated/dashboard";
import { useApiMutation, useApiQuery } from "@/api/queries";
import { IconButton } from "@/components/IconButton/IconButton";
import { Panel } from "@/components/Panel/Panel";
import { StatusPanel } from "@/components/StatusPanel/StatusPanel";
import { Toast } from "@/components/Toast/Toast";
import type { Notice } from "@/types";

import { TemplateModal } from "./TemplateModal";
import { TemplatesList } from "./TemplatesList";

const ADD_LABEL = "Add template";
const TITLE = "SMS Templates";

export function TemplatesScreen() {
  const [editing, setEditing] = useState<Template>();
  const [adding, setAdding] = useState(false);
  const [notice, setNotice] = useState<Notice>();
  const templates = useApiQuery("get", "/api/app/templates");
  const remove = useApiMutation("delete", "/api/app/templates/{templateId}");

  if (templates.data === undefined) {
    return <StatusPanel title={TITLE} />;
  }
  if (templates.data.status === "ERROR") {
    return <StatusPanel error={templates.data.message} title={TITLE} />;
  }

  const add = () => {
    setAdding(true);
  };
  const close = () => {
    setAdding(false);
    setEditing(undefined);
  };
  const saved = (sent: Notice) => {
    setNotice(sent);
    close();
  };
  const addButton = <IconButton icon="plus" label={ADD_LABEL} onClick={add} variant="primary" />;

  return (
    <Panel actions={addButton} title={TITLE}>
      <Toast
        notice={notice}
        onDismiss={() => {
          setNotice(undefined);
        }}
      />
      <TemplatesList
        onAdd={add}
        onDelete={(template) => {
          remove.mutate({ params: { path: { templateId: template.templateId } } });
        }}
        onEdit={setEditing}
        rows={templates.data.data}
      />
      {adding || editing !== undefined ? (
        <TemplateModal onClose={close} onSaved={saved} template={editing} />
      ) : null}
    </Panel>
  );
}
