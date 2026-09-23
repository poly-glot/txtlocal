import { useRef, useState } from "react";

import { Button } from "@/components/Button/Button";
import type { IconName } from "@/components/Icon/Icon";
import { IconButton } from "@/components/IconButton/IconButton";
import { useDismiss } from "@/lib/useDismiss";

import styles from "./ActionMenu.module.css";

type Align = "end" | "start";
type Emphasis = "ghost" | "primary";

export interface MenuItem {
  label: string;
  value: string;
}

interface Props {
  align?: Align;
  disabled?: boolean;
  emphasis?: Emphasis;
  icon?: IconName;
  items: readonly MenuItem[];
  label: string;
  onPick: (value: string) => void;
}

export function ActionMenu({
  align = "end",
  disabled = false,
  emphasis = "ghost",
  icon,
  items,
  label,
  onPick,
}: Props) {
  const menu = useRef<HTMLDivElement>(null);
  const [open, setOpen] = useState(false);

  useDismiss(menu, open, setOpen);

  const toggle = () => {
    setOpen(!open);
  };

  return (
    <div className={styles.menu} ref={menu}>
      {icon === undefined ? (
        <Button aria-expanded={open} disabled={disabled} onClick={toggle} variant="secondary">
          {label}
        </Button>
      ) : (
        <IconButton
          aria-expanded={open}
          disabled={disabled}
          icon={icon}
          label={label}
          onClick={toggle}
          variant={emphasis}
        />
      )}
      {open ? (
        <ul className={styles.items} data-align={align}>
          {items.map((item) => (
            <li key={item.value}>
              <button
                className={styles.pick}
                onClick={() => {
                  setOpen(false);
                  onPick(item.value);
                }}
                type="button"
              >
                {item.label}
              </button>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
