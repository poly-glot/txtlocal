import type { ReactNode } from "react";

import styles from "./Icon.module.css";

const GLYPHS = {
  alert: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 8v5" />
      <path d="M12 16h.01" />
    </>
  ),
  back: <path d="m14 6-6 6 6 6" />,
  bell: (
    <>
      <path d="M6.5 10a5.5 5.5 0 0 1 11 0c0 4 1.5 5.5 1.5 5.5H5S6.5 14 6.5 10Z" />
      <path d="M10.5 19a1.8 1.8 0 0 0 3 0" />
    </>
  ),
  brand: (
    <path d="M21 11.5a8.4 8.4 0 0 1-9 8.4 8.8 8.8 0 0 1-3.8-.9L3 20.5l1.6-4.9A8.4 8.4 0 0 1 12 3.1a8.4 8.4 0 0 1 9 8.4Z" />
  ),
  check: <path d="m5 12.5 4.5 4.5L19 7" />,
  chevron: <path d="m6 9 6 6 6-6" />,
  close: (
    <>
      <path d="m6 6 12 12" />
      <path d="M18 6 6 18" />
    </>
  ),
  code: (
    <>
      <path d="m9 8-5 4 5 4" />
      <path d="m15 8 5 4-5 4" />
    </>
  ),
  contacts: (
    <>
      <circle cx="9" cy="8" r="3.2" />
      <path d="M3.5 19.5a5.5 5.5 0 0 1 11 0" />
      <path d="M16 5.5a3.2 3.2 0 0 1 0 6" />
      <path d="M17.5 14.6a5.5 5.5 0 0 1 3 4.9" />
    </>
  ),
  document: (
    <>
      <path d="M7 3.5h7l4 4v13H7Z" />
      <path d="M14 3.5v4h4" />
      <path d="M10 12h5" />
      <path d="M10 15.5h5" />
    </>
  ),
  external: (
    <>
      <path d="M14 4h6v6" />
      <path d="M20 4 11 13" />
      <path d="M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5" />
    </>
  ),
  hash: (
    <>
      <path d="M5 9h14" />
      <path d="M5 15h14" />
      <path d="M10 4 8.5 20" />
      <path d="M15.5 4 14 20" />
    </>
  ),
  help: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M9.6 9.5a2.5 2.5 0 0 1 4.8.8c0 1.7-2.4 2-2.4 3.4" />
      <path d="M12 17h.01" />
    </>
  ),
  home: (
    <>
      <path d="M3 10.5 12 3l9 7.5" />
      <path d="M5.5 9.5V21h13V9.5" />
    </>
  ),
  image: (
    <>
      <rect height="14" rx="2" width="17" x="3.5" y="5" />
      <circle cx="9" cy="10" r="1.6" />
      <path d="m5 17 4.5-4.5 3 3L16 12l3.5 3.5" />
    </>
  ),
  info: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 11v5" />
      <path d="M12 8h.01" />
    </>
  ),
  key: (
    <>
      <circle cx="8" cy="12" r="3.5" />
      <path d="M11.5 12H20" />
      <path d="M17 12v3" />
      <path d="M14 12v2.5" />
    </>
  ),
  message: (
    <path d="M20 12.5a7.5 7.5 0 0 1-8 7.4 8 8 0 0 1-3.4-.8L4.5 20.5l1.4-4A7.5 7.5 0 0 1 12 4.5a7.5 7.5 0 0 1 8 8Z" />
  ),
  more: (
    <>
      <circle cx="5.5" cy="12" r="1.2" />
      <circle cx="12" cy="12" r="1.2" />
      <circle cx="18.5" cy="12" r="1.2" />
    </>
  ),
  play: <path d="M8 5.5v13l11-6.5-11-6.5Z" fill="currentColor" stroke="none" />,
  plus: (
    <>
      <path d="M12 5v14" />
      <path d="M5 12h14" />
    </>
  ),
  send: (
    <>
      <path d="M20.5 3.5 3.5 10.2l7 2.3 2.3 7 7.7-16Z" />
      <path d="M10.5 12.5 20.5 3.5" />
    </>
  ),
  signal: (
    <>
      <path d="M5 17v-3" />
      <path d="M10 17v-6" />
      <path d="M15 17v-9" />
      <path d="M20 17V6" />
    </>
  ),
} satisfies Record<string, ReactNode>;

export type IconName = keyof typeof GLYPHS;

type IconSize = 12 | 14 | 16 | 20;

interface Props {
  name: IconName;
  size?: IconSize;
}

export function Icon({ name, size = 16 }: Props) {
  return (
    <svg
      aria-hidden="true"
      className={styles.icon}
      data-size={size}
      focusable="false"
      height={size}
      viewBox="0 0 24 24"
      width={size}
    >
      {GLYPHS[name]}
    </svg>
  );
}
