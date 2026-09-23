import { useState } from "react";

import { useApiMutation } from "@/api/queries";
import { Button } from "@/components/Button/Button";
import { Input } from "@/components/Input/Input";
import { Modal } from "@/components/Modal/Modal";
import { Toast } from "@/components/Toast/Toast";
import { refusalNotice } from "@/lib/notice";
import type { Notice } from "@/types";

import { NO_IMPORTS, chunksOf, importRows, importSummary, withReport } from "./rules";

import styles from "./ImportModal.module.css";

const CLOSE_LABEL = "Close";
const FILE_LABEL = "CSV file";
const HINT =
  "A CSV with a header row: mobile, first_name, last_name, email, cf1, cf2, cf3 and cf4.";
const IMPORT_LABEL = "IMPORT";
const TITLE = "Import contacts";
const TITLE_ID = "import-modal-title";

interface Props {
  listId: string;
  onClose: () => void;
}

export function ImportModal({ listId, onClose }: Props) {
  const [file, setFile] = useState<File>();
  const [notice, setNotice] = useState<Notice>();
  const [report, setReport] = useState<string>();
  const upload = useApiMutation("post", "/api/app/lists/{listId}/contacts/import");

  const run = async (chosen: File) => {
    setReport(undefined);

    const parsed = importRows(await chosen.text());
    if (parsed.status === "ERROR") {
      setNotice(refusalNotice(parsed));
      return;
    }

    let totals = NO_IMPORTS;
    for (const rows of chunksOf(parsed.data)) {
      const result = await upload.mutateAsync({
        body: { rows: [...rows] },
        params: { path: { listId } },
      });
      if (result.status === "ERROR") {
        setNotice(refusalNotice(result));
        return;
      }
      totals = withReport(totals, result.data);
    }
    setReport(importSummary(totals));
  };

  return (
    <Modal labelledBy={TITLE_ID} onClose={onClose}>
      <form
        onSubmit={(event) => {
          event.preventDefault();
          if (file !== undefined) {
            void run(file);
          }
        }}
      >
        <Modal.Header>
          <Modal.Title id={TITLE_ID}>{TITLE}</Modal.Title>
        </Modal.Header>
        <Modal.Body>
          <Input
            accept=".csv,text/csv"
            helper={HINT}
            id="import-file"
            label={FILE_LABEL}
            onChange={(event) => {
              setFile(event.target.files?.[0]);
            }}
            type="file"
          />
          {report === undefined ? null : (
            <p className={styles.report} role="status">
              {report}
            </p>
          )}
          <Toast
            notice={notice}
            onDismiss={() => {
              setNotice(undefined);
            }}
          />
        </Modal.Body>
        <Modal.Footer>
          <Button onClick={onClose} variant="secondary">
            {CLOSE_LABEL}
          </Button>
          <Button disabled={file === undefined || upload.isPending} type="submit">
            {IMPORT_LABEL}
          </Button>
        </Modal.Footer>
      </form>
    </Modal>
  );
}
