import type { ReactNode } from "react";

import { Icon } from "@/components/Icon/Icon";

import styles from "./StepSection.module.css";

const COMPLETE_LABEL = "Complete";
const INCOMPLETE_LABEL = "Not complete";

interface Props {
  children: ReactNode;
  complete: boolean;
  step: number;
  subtitle: string;
  title: string;
}

export function StepSection({ children, complete, step, subtitle, title }: Props) {
  return (
    <section aria-label={title} className={styles.step}>
      <header className={styles.intro}>
        <span aria-hidden="true" className={styles.mark} data-complete={complete}>
          {complete ? <Icon name="check" size={14} /> : step}
        </span>
        <div className={styles.heading}>
          <h3 className={styles.title}>{title}</h3>
          <p className={styles.subtitle}>{subtitle}</p>
          <p className={styles.state}>{complete ? COMPLETE_LABEL : INCOMPLETE_LABEL}</p>
        </div>
      </header>
      <div className={styles.body}>{children}</div>
    </section>
  );
}
