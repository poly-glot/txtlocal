import type { ReactNode } from "react";

import styles from "./Badge.module.css";

export type Tone = "accent" | "danger" | "neutral" | "success" | "warning";

interface Props {
  children: ReactNode;
  tone?: Tone;
}

export function Badge({ children, tone = "neutral" }: Props) {
  return (
    <span className={styles.badge} data-tone={tone}>
      {children}
    </span>
  );
}
