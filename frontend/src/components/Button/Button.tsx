import type { ButtonHTMLAttributes } from "react";

import styles from "./Button.module.css";

type Variant = "danger" | "primary" | "secondary" | "tonal";

interface Props extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, "className"> {
  variant?: Variant;
}

export function Button({ children, type = "button", variant = "primary", ...rest }: Props) {
  return (
    <button {...rest} className={styles.button} data-variant={variant} type={type}>
      {children}
    </button>
  );
}
