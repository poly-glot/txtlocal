import { useState } from "react";

import type { Campaign, SendersView } from "@/api/generated/dashboard";
import { Panel } from "@/components/Panel/Panel";
import { Toast } from "@/components/Toast/Toast";
import { refusalNotice } from "@/lib/notice";
import type { Notice } from "@/types";

import type { ScreenProduct } from "../../rules";
import { EditorHeader } from "./EditorHeader";
import { EditorSteps } from "./EditorSteps";
import { SaveDraftDialog } from "./SaveDraftDialog";
import { ScheduleActions } from "./ScheduleActions";
import { useCampaignDraft } from "./useCampaignDraft";

const SAVED_NOTICE: Notice = { message: "Draft saved.", tone: "success" };

interface Props {
  campaign: Campaign | undefined;
  onClose: () => void;
  product: ScreenProduct;
  senders: SendersView;
}

export function CampaignForm({ campaign, onClose, product, senders }: Props) {
  const [leaving, setLeaving] = useState(false);
  const [notice, setNotice] = useState<Notice>();
  const editor = useCampaignDraft(campaign, product);

  const persist = async (then: () => void) => {
    const saved = await editor.save();
    if (saved.status === "ERROR") {
      setNotice(refusalNotice(saved));

      return;
    }
    setLeaving(false);
    then();
  };

  const next = async () => {
    const priced = await editor.next();
    if (priced.status === "ERROR") {
      setNotice(refusalNotice(priced));
    }
  };

  const leave = () => {
    setLeaving(editor.dirty);
    if (!editor.dirty) {
      onClose();
    }
  };

  return (
    <Panel>
      <EditorHeader
        name={editor.draft.name}
        onBack={leave}
        onNameChange={(name) => {
          editor.patch({ name });
        }}
        onSaveDraft={() => {
          void persist(() => {
            setNotice(SAVED_NOTICE);
          });
        }}
      />
      <Toast
        notice={notice}
        onDismiss={() => {
          setNotice(undefined);
        }}
      />
      <EditorSteps
        draft={editor.draft}
        onNext={() => {
          void next();
        }}
        onPatch={editor.patch}
        product={product}
        senders={senders}
      />
      <ScheduleActions
        campaignId={editor.savedId}
        name={editor.draft.name}
        onScheduled={onClose}
        quote={editor.quoted}
      />
      {leaving ? (
        <SaveDraftDialog
          onClose={() => {
            setLeaving(false);
          }}
          onDiscard={() => {
            editor.discard();
            onClose();
          }}
          onSave={() => {
            void persist(onClose);
          }}
        />
      ) : null}
    </Panel>
  );
}
