import type { Notice } from "@/types";

import styles from "./Toast.module.css";

interface Props {
  notice: Notice | undefined;
  onDismiss: () => void;
}

export function Toast({ notice, onDismiss }: Props) {
  if (notice === undefined) {
    return null;
  }

  return (
    <div
      className={styles.toast}
      data-tone={notice.tone}
      role={notice.tone === "error" ? "alert" : "status"}
    >
      <span className={styles.message}>{notice.message}</span>
      <button aria-label="Dismiss" className={styles.dismiss} onClick={onDismiss} type="button">
        ×
      </button>
    </div>
  );
}
