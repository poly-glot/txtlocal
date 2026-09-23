import { useState } from "react";
import type { ReactNode } from "react";
import { NavLink, useLocation } from "react-router";

import { Icon } from "@/components/Icon/Icon";
import type { IconName } from "@/components/Icon/Icon";

import { isGroup } from "../navigation";
import type { NavEntry, NavGroup, NavLeaf } from "../navigation";
import { isRouteInGroup } from "./rules";

import styles from "./SidebarEntry.module.css";

interface Props {
  entry: NavEntry;
}

interface GroupProps {
  group: NavGroup;
}

interface LeafProps {
  children?: ReactNode;
  leaf: NavLeaf;
}

interface GlyphProps {
  name: IconName;
}

export function SidebarEntry({ entry }: Props) {
  if (isGroup(entry)) {
    return <Group group={entry} />;
  }

  return (
    <Leaf leaf={entry}>
      <Glyph name={entry.icon} />
    </Leaf>
  );
}

function Group({ group }: GroupProps) {
  const { pathname } = useLocation();
  const [openOnMount] = useState(() => isRouteInGroup(group, pathname));

  return (
    <details className={styles.group} open={openOnMount}>
      <summary className={styles.row}>
        <Glyph name={group.icon} />
        <span className={styles.label}>{group.label}</span>
        <span className={styles.chevron}>
          <Icon name="chevron" size={14} />
        </span>
      </summary>
      <ul className={styles.sublist}>
        {group.children.map((leaf) => (
          <li key={leaf.label}>
            <Leaf leaf={leaf} />
          </li>
        ))}
      </ul>
    </details>
  );
}

function Leaf({ children, leaf }: LeafProps) {
  return (
    <NavLink className={() => styles.row} end to={leaf.path}>
      {children}
      <span className={styles.label}>{leaf.label}</span>
    </NavLink>
  );
}

function Glyph({ name }: GlyphProps) {
  return (
    <span className={styles.glyph}>
      <Icon name={name} />
    </span>
  );
}
