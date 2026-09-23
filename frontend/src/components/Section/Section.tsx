import { useId } from "react";
import type { ReactNode } from "react";

import styles from "./Section.module.css";

interface Props {
  children: ReactNode;
  title: string;
}

export function Section({ children, title }: Props) {
  const titleId = useId();

  return (
    <section aria-labelledby={titleId} className={styles.section}>
      <h3 className={styles.title} id={titleId}>
        {title}
      </h3>
      <div className={styles.content}>{children}</div>
    </section>
  );
}
