import { useState } from "react";

import { Icon } from "@/components/Icon/Icon";

import { SIDEBAR } from "../navigation";
import { SidebarEntry } from "./SidebarEntry";

import styles from "./Sidebar.module.css";

const BRAND = "txtlocal";
const COLLAPSE_LABEL = "Collapse sidebar";
const EXPAND_LABEL = "Expand sidebar";
const NARROW_VIEWPORT_QUERY = "(max-width: 900px)";

const isNarrowViewport = () => window.matchMedia(NARROW_VIEWPORT_QUERY).matches;

export function Sidebar() {
  const [collapsed, setCollapsed] = useState(isNarrowViewport);

  return (
    <aside className={styles.sidebar} data-collapsed={collapsed}>
      <div className={styles.brand}>
        <span className={styles.tile}>
          <Icon name="brand" />
        </span>
        <span className={styles.name} hidden={collapsed}>
          {BRAND}
        </span>
      </div>
      <nav aria-label="Main" className={styles.nav} hidden={collapsed}>
        <ul className={styles.list}>
          {SIDEBAR.map((entry) => (
            <li className={styles.item} data-starts-section={entry.startsSection} key={entry.label}>
              <SidebarEntry entry={entry} />
            </li>
          ))}
        </ul>
      </nav>
      <button
        aria-label={collapsed ? EXPAND_LABEL : COLLAPSE_LABEL}
        className={styles.collapse}
        onClick={() => {
          setCollapsed(!collapsed);
        }}
        type="button"
      >
        <Icon name="back" />
      </button>
    </aside>
  );
}
