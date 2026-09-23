import { useState } from "react";

import { useApiMutation } from "@/api/queries";
import { ActionMenu } from "@/components/ActionMenu/ActionMenu";
import { Toast } from "@/components/Toast/Toast";
import { saveCsv } from "@/lib/download";
import { refusalNotice } from "@/lib/notice";
import type { Notice } from "@/types";

import type { HistoryQuery } from "./rules";

const CSV_ITEMS = [{ label: "CSV", value: "CSV" }];
const EXPORT_FILENAME = "sms-history.csv";
const EXPORT_LABEL = "EXPORT ▾";

interface Props {
  filters: HistoryQuery;
}

export function HistoryExport({ filters }: Props) {
  const [notice, setNotice] = useState<Notice>();
  const exporting = useApiMutation("get", "/api/app/messages/export");

  const download = () => {
    exporting.mutate(
      { params: { query: filters }, parseAs: "text" },
      {
        onSuccess: (result) => {
          if (result.status === "ERROR") {
            setNotice(refusalNotice(result));
            return;
          }
          saveCsv(result.data, EXPORT_FILENAME);
        },
      },
    );
  };

  return (
    <>
      <ActionMenu items={CSV_ITEMS} label={EXPORT_LABEL} onPick={download} />
      <Toast
        notice={notice}
        onDismiss={() => {
          setNotice(undefined);
        }}
      />
    </>
  );
}
