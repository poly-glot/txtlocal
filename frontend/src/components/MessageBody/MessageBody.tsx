import type { ReactNode } from "react";

import styles from "./MessageBody.module.css";

interface Props {
  children: ReactNode;
  id: string;
  label: string;
  onChange: (body: string) => void;
  toolbar?: ReactNode;
  value: string;
}

export function MessageBody({ children, id, label, onChange, toolbar, value }: Props) {
  return (
    <div className={styles.field}>
      <label className={styles.label} htmlFor={id}>
        {label}
      </label>
      {toolbar}
      <textarea
        className={styles.textarea}
        id={id}
        onChange={(event) => {
          onChange(event.target.value);
        }}
        value={value}
      />
      <p className={styles.footer}>{children}</p>
    </div>
  );
}
