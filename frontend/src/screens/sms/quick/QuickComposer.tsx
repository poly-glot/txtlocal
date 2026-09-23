import { useState } from "react";
import type { ComponentType } from "react";

import type { SendersView } from "@/api/generated/dashboard";
import { Button } from "@/components/Button/Button";
import { Icon } from "@/components/Icon/Icon";
import { PhonePreview } from "@/components/PhonePreview/PhonePreview";
import { Toast } from "@/components/Toast/Toast";
import type { Notice } from "@/types";

import type { ScreenProduct } from "../rules";
import { senderDisplayOf } from "../rules";
import { ConfirmSendModal } from "./ConfirmSendModal";
import type { Draft } from "./rules";
import { emptyDraft, isSendable } from "./rules";

import styles from "./QuickComposer.module.css";

const CONFIRM_LABEL = "PREVIEW AND CONFIRM";

export interface QuickFormProps {
  draft: Draft;
  onNotice: (notice: Notice) => void;
  onPatch: (change: Partial<Draft>) => void;
  senders: SendersView["senders"];
}

interface Props {
  Form: ComponentType<QuickFormProps>;
  kind: ScreenProduct;
  timezone: string | undefined;
  view: SendersView;
}

export function QuickComposer({ Form, kind, timezone, view }: Props) {
  const [draft, setDraft] = useState(() => emptyDraft(kind));
  const [confirming, setConfirming] = useState(false);
  const [notice, setNotice] = useState<Notice>();

  const finish = (sent: Notice) => {
    setNotice(sent);
    setConfirming(false);
    if (sent.tone === "success") {
      setDraft(emptyDraft(kind));
    }
  };

  return (
    <>
      <Toast
        notice={notice}
        onDismiss={() => {
          setNotice(undefined);
        }}
      />
      <div className={styles.split}>
        <div className={styles.form}>
          <Form
            draft={draft}
            onNotice={setNotice}
            onPatch={(change) => {
              setDraft({ ...draft, ...change });
            }}
            senders={view.senders}
          />
          <Button
            disabled={!isSendable(draft)}
            onClick={() => {
              setConfirming(true);
            }}
          >
            <Icon name="send" />
            {CONFIRM_LABEL}
          </Button>
        </div>
        <PhonePreview body={draft.body} title={senderDisplayOf(view, draft.senderId)} />
      </div>
      {confirming ? (
        <ConfirmSendModal
          draft={draft}
          onClose={() => {
            setConfirming(false);
          }}
          onSent={finish}
          timezone={timezone}
        />
      ) : null}
    </>
  );
}
