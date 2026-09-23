import { useState } from "react";

import type { SendersView } from "@/api/generated/dashboard";
import { useApiMutation } from "@/api/queries";
import { Button } from "@/components/Button/Button";
import { Toast } from "@/components/Toast/Toast";
import type { Notice } from "@/types";

import { NumbersSection } from "../NumbersSection";
import { enabledCountriesOf, sendersOf } from "../rules";
import { AddOwnNumberModal } from "./AddOwnNumberModal";
import { DedicatedNumbersSection } from "./DedicatedNumbersSection";
import { OwnNumbersTable } from "./OwnNumbersTable";
import { SharedNumbersTable } from "./SharedNumbersTable";
import type { OwnNumberDraft } from "./rules";
import { emptyOwnNumber, reverifyDraft } from "./rules";

import styles from "./MyNumbersTab.module.css";

const ADD_LABEL = "+ Add";
const FALLBACK_COUNTRY = "GB";
const OWN_COPY = "Connect your own mobile numbers with txtlocal for easy messaging.";
const SHARED_COPY =
  "Use free shared numbers for cost effective SMS. Ideal for bulk messaging and promotions.";

interface Props {
  view: SendersView;
}

export function MyNumbersTab({ view }: Props) {
  const [draft, setDraft] = useState<OwnNumberDraft>();
  const [notice, setNotice] = useState<Notice>();
  const [defaultCountry = FALLBACK_COUNTRY] = enabledCountriesOf(view);
  const remove = useApiMutation("delete", "/api/app/senders/{senderId}");

  const removeAndReport = (senderId: string) => {
    remove.mutate(
      { params: { path: { senderId } } },
      {
        onSuccess: (result) => {
          if (result.status === "ERROR") {
            setNotice({ message: result.message, tone: "error" });
          }
        },
      },
    );
  };

  return (
    <div className={styles.sections}>
      <DedicatedNumbersSection
        onCancel={(sender) => {
          removeAndReport(sender.senderId);
        }}
        rows={sendersOf(view, "DEDICATED")}
      />
      <NumbersSection
        action={
          <Button
            onClick={() => {
              setDraft(emptyOwnNumber(defaultCountry));
            }}
          >
            {ADD_LABEL}
          </Button>
        }
        copy={OWN_COPY}
        title="Own Numbers"
      >
        <OwnNumbersTable
          onRemove={(sender) => {
            removeAndReport(sender.senderId);
          }}
          onReverify={(sender) => {
            setDraft(reverifyDraft(sender));
          }}
          rows={sendersOf(view, "OWN")}
        />
      </NumbersSection>
      <NumbersSection copy={SHARED_COPY} title="Shared Numbers">
        <SharedNumbersTable rows={sendersOf(view, "SHARED")} />
      </NumbersSection>
      <Toast
        notice={notice}
        onDismiss={() => {
          setNotice(undefined);
        }}
      />
      {draft === undefined ? null : (
        <AddOwnNumberModal
          initial={draft}
          onClose={() => {
            setDraft(undefined);
          }}
        />
      )}
    </div>
  );
}
