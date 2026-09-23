import type { ButtonHTMLAttributes } from "react";

import { Icon } from "@/components/Icon/Icon";
import type { IconName } from "@/components/Icon/Icon";

import styles from "./IconButton.module.css";

type Variant = "ghost" | "primary";

interface Props extends Omit<
  ButtonHTMLAttributes<HTMLButtonElement>,
  "aria-label" | "children" | "className"
> {
  icon: IconName;
  label: string;
  variant?: Variant;
}

export function IconButton({ icon, label, type = "button", variant = "ghost", ...rest }: Props) {
  return (
    <button
      {...rest}
      aria-label={label}
      className={styles.button}
      data-variant={variant}
      type={type}
    >
      <Icon name={icon} size={20} />
    </button>
  );
}
