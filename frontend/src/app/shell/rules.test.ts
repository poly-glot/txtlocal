import { describe, expect, it } from "vitest";

import { ME } from "@/test/fixtures/identity";

import type { NavGroup } from "../navigation";
import { avatarMenuFor, initialOf, isRouteInGroup, titleOf } from "./rules";

const SMS_GROUP: NavGroup = {
  children: [{ label: "Quick SMS", path: "/sms/quick" }],
  icon: "message",
  label: "SMS",
};

describe("titleOf", () => {
  it.each([
    { label: "names the home page", pathname: "/", title: "Home" },
    { label: "names a sidebar page", pathname: "/sms/quick", title: "Quick SMS" },
    {
      label: "names a page under a sidebar page after that page",
      pathname: "/sms/campaigns/campaign-1",
      title: "SMS Campaign",
    },
    { label: "names a billing tab after Billing", pathname: "/billing/usage", title: "Billing" },
    {
      label: "keeps the first label of a path two entries share",
      pathname: "/account",
      title: "Account Settings",
    },
    { label: "falls back to Home for an unknown page", pathname: "/unknown/page", title: "Home" },
  ] as const)("$label", ({ pathname, title }) => {
    expect(titleOf(pathname)).toBe(title);
  });
});

describe("isRouteInGroup", () => {
  it.each([
    { held: true, label: "holds its own page", pathname: "/sms/quick" },
    { held: true, label: "holds a page under its page", pathname: "/sms/quick/confirm" },
    {
      held: false,
      label: "does not hold a path that only shares a prefix",
      pathname: "/sms/quickly",
    },
    { held: false, label: "does not hold another page", pathname: "/contacts" },
  ] as const)("$label", ({ held, pathname }) => {
    expect(isRouteInGroup(SMS_GROUP, pathname)).toBe(held);
  });
});

describe("avatarMenuFor", () => {
  it.each([
    { billing: true, label: "shows Billing to the owner", role: "OWNER" },
    { billing: false, label: "hides Billing from a sub-account", role: "SUB" },
  ] as const)("$label", ({ billing, role }) => {
    const labels = avatarMenuFor(role).map((entry) => entry.label);

    expect(labels.includes("Billing")).toBe(billing);
    expect(labels).toContain("My Profile");
  });
});

describe("initialOf", () => {
  it.each([
    { expected: "D", firstName: "Demo", label: "takes the first name's initial" },
    { expected: "Z", firstName: "", label: "falls back to the username's initial, upper-cased" },
  ] as const)("$label", ({ expected, firstName }) => {
    expect(initialOf({ ...ME, firstName, username: "zed@txtlocal.local" })).toBe(expected);
  });
});
