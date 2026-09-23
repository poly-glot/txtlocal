import type { ButtonHTMLAttributes } from "react";

import styles from "./RowAction.module.css";

type Tone = "brand" | "danger";

interface Props extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, "className" | "type"> {
  tone?: Tone;
}

export function RowAction({ children, tone = "brand", ...rest }: Props) {
  return (
    <button {...rest} className={styles.action} data-tone={tone} type="button">
      {children}
    </button>
  );
}
