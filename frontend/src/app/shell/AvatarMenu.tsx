import { useRef, useState } from "react";
import { Link, useLocation } from "react-router";

import type { MeView } from "@/api/generated/dashboard";
import { signOut } from "@/lib/auth";
import { useDismiss } from "@/lib/useDismiss";

import { avatarMenuFor, initialOf } from "./rules";

import styles from "./AvatarMenu.module.css";

const LOGOUT = "Logout";
const MENU_LABEL = "Account menu";

interface Props {
  me: MeView;
}

export function AvatarMenu({ me }: Props) {
  const { pathname } = useLocation();

  return <AccountMenu key={pathname} me={me} />;
}

function AccountMenu({ me }: Props) {
  const menu = useRef<HTMLDetailsElement>(null);
  const [open, setOpen] = useState(false);
  const entries = avatarMenuFor(me.role);

  useDismiss(menu, open, setOpen);

  return (
    <details
      className={styles.menu}
      onToggle={(event) => {
        setOpen(event.currentTarget.open);
      }}
      open={open}
      ref={menu}
    >
      <summary aria-label={MENU_LABEL} className={styles.avatar}>
        {initialOf(me)}
        <span aria-hidden="true" className={styles.presence} />
      </summary>
      <ul className={styles.items}>
        <li className={styles.userId}>User ID: {me.userId}</li>
        {entries.map((entry) => (
          <li className={styles.entry} key={entry.label}>
            <Link className={styles.item} to={entry.path}>
              {entry.label}
            </Link>
          </li>
        ))}
        <li className={styles.entry}>
          <button className={styles.item} onClick={signOut} type="button">
            {LOGOUT}
          </button>
        </li>
      </ul>
    </details>
  );
}
