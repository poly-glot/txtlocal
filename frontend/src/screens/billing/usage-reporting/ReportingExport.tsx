import { useId, useState } from "react";

import { useApiMutation } from "@/api/queries";
import { Button } from "@/components/Button/Button";
import { Icon } from "@/components/Icon/Icon";
import { Toast } from "@/components/Toast/Toast";
import { saveCsv } from "@/lib/download";
import type { Notice } from "@/types";

import type { ReportingFilterState } from "./rules";
import { reportingFilterQuery } from "./rules";

import styles from "./ReportingExport.module.css";

const EXPORT_FILENAME = "usage-reporting.csv";
const EXPORT_HINT = "Exports the current filter as CSV";
const EXPORT_LABEL = "EXPORT";

interface Props {
  filters: ReportingFilterState;
}

export function ReportingExport({ filters }: Props) {
  const hintId = useId();
  const [notice, setNotice] = useState<Notice>();
  const exporting = useApiMutation("get", "/api/app/analytics/reporting/export");

  const download = () => {
    const query = reportingFilterQuery(filters);
    exporting.mutate(
      { params: { query }, parseAs: "text" },
      {
        onSuccess: (result) => {
          if (result.status === "ERROR") {
            setNotice({ message: result.message, tone: "error" });
            return;
          }
          saveCsv(result.data, EXPORT_FILENAME);
        },
      },
    );
  };

  return (
    <div className={styles.export}>
      <div className={styles.action}>
        <Button
          aria-describedby={hintId}
          disabled={exporting.isPending}
          onClick={download}
          variant="secondary"
        >
          {EXPORT_LABEL}
        </Button>
        <span className={styles.hint}>
          <Icon name="info" />
          <span className={styles.tip} id={hintId} role="tooltip">
            {EXPORT_HINT}
          </span>
        </span>
      </div>
      <Toast
        notice={notice}
        onDismiss={() => {
          setNotice(undefined);
        }}
      />
    </div>
  );
}
