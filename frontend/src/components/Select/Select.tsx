import type { SelectHTMLAttributes } from "react";

import styles from "./Select.module.css";

export interface Option {
  label: string;
  value: string;
}

interface Props extends Omit<
  SelectHTMLAttributes<HTMLSelectElement>,
  "children" | "className" | "id"
> {
  helper?: string;
  id: string;
  label: string;
  labelHidden?: boolean;
  options: readonly Option[];
}

export function Select({ helper, id, label, labelHidden = false, options, ...rest }: Props) {
  const helperId = `${id}-helper`;

  return (
    <div className={styles.field}>
      <label className={labelHidden ? styles.hiddenLabel : styles.label} htmlFor={id}>
        {label}
      </label>
      <select
        {...rest}
        aria-describedby={helper === undefined ? undefined : helperId}
        className={styles.select}
        id={id}
      >
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
      {helper === undefined ? null : (
        <p className={styles.helper} id={helperId}>
          {helper}
        </p>
      )}
    </div>
  );
}
