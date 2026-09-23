import { useId } from "react";
import type { ReactNode } from "react";

import styles from "./Panel.module.css";

interface Props {
  actions?: ReactNode;
  children: ReactNode;
  title?: string | undefined;
}

export function Panel({ actions, children, title }: Props) {
  const titleId = useId();
  const hasTitle = title !== undefined;

  return (
    <section aria-labelledby={hasTitle ? titleId : undefined} className={styles.panel}>
      {hasTitle ? (
        <header className={styles.header}>
          <h2 className={styles.title} id={titleId}>
            {title}
          </h2>
          {actions}
        </header>
      ) : null}
      {children}
    </section>
  );
}
