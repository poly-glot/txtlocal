import type { MeView, Role } from "@/api/generated/dashboard";

import { AVATAR_MENU, SIDEBAR, leavesOf } from "../navigation";
import type { NavGroup, NavLeaf } from "../navigation";

const titles = new Map<string, string>();
for (const leaf of [...leavesOf(SIDEBAR), ...AVATAR_MENU]) {
  if (!titles.has(leaf.path)) {
    titles.set(leaf.path, leaf.label);
  }
}

export function isRouteInGroup(group: NavGroup, pathname: string): boolean {
  return group.children.some(
    (leaf) => pathname === leaf.path || pathname.startsWith(`${leaf.path}/`),
  );
}

export function titleOf(pathname: string): string {
  let path = pathname;
  while (path !== "") {
    const title = titles.get(path);
    if (title !== undefined) {
      return title;
    }
    path = path.slice(0, path.lastIndexOf("/"));
  }

  return titles.get("/") ?? "";
}

export function avatarMenuFor(role: Role): NavLeaf[] {
  return AVATAR_MENU.filter((entry) => role === "OWNER" || entry.ownerOnly !== true);
}

export function initialOf(me: MeView): string {
  const name = me.firstName === "" ? me.username : me.firstName;

  return name.charAt(0).toUpperCase();
}
