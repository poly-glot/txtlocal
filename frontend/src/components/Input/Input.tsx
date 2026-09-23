import type { InputHTMLAttributes } from "react";

import styles from "./Input.module.css";

interface Props extends Omit<InputHTMLAttributes<HTMLInputElement>, "className" | "id"> {
  helper?: string;
  id: string;
  label: string;
  labelHidden?: boolean;
}

export function Input({ helper, id, label, labelHidden = false, ...rest }: Props) {
  const helperId = `${id}-helper`;

  return (
    <div className={styles.field}>
      <label className={labelHidden ? styles.hiddenLabel : styles.label} htmlFor={id}>
        {label}
      </label>
      <input
        {...rest}
        aria-describedby={helper === undefined ? undefined : helperId}
        className={styles.input}
        id={id}
      />
      {helper === undefined ? null : (
        <p className={styles.helper} id={helperId}>
          {helper}
        </p>
      )}
    </div>
  );
}
