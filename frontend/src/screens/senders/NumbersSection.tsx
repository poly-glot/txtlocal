import type { ReactNode } from "react";

import styles from "./NumbersSection.module.css";

interface Props {
  action?: ReactNode;
  children?: ReactNode;
  copy: string;
  title: string;
}

export function NumbersSection({ action, children, copy, title }: Props) {
  const headingId = `senders-${title.toLowerCase().replaceAll(" ", "-")}`;

  return (
    <section aria-labelledby={headingId} className={styles.section}>
      <header className={styles.header}>
        <h2 className={styles.title} id={headingId}>
          {title}
        </h2>
        {action}
      </header>
      <p className={styles.copy}>{copy}</p>
      {children}
    </section>
  );
}
