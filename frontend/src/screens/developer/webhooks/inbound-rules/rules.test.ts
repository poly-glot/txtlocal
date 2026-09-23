import { describe, expect, it } from "vitest";

import { DEFAULT_RULE } from "@/test/fixtures/automation";

import { actionFieldFor, toggledInboundRule } from "./rules";

describe("actionFieldFor", () => {
  it.each([
    {
      action: "AUTO_REPLY",
      kind: "textarea",
      label: "Reply message",
      required: true,
      target: "actionAddress",
    },
    {
      action: "EMAIL_FIXED",
      kind: "email",
      label: "Email Address",
      required: true,
      target: "actionAddress",
    },
    {
      action: "EMAIL_USER",
      kind: "email",
      label: "Back-up Email Address",
      required: false,
      target: "backupEmail",
    },
    { action: "GROUP_SMS", kind: "list", label: "List", required: true, target: "actionAddress" },
    {
      action: "MOVE_CONTACT",
      kind: "list",
      label: "List",
      required: true,
      target: "actionAddress",
    },
    {
      action: "SMS",
      kind: "text",
      label: "Forward to number",
      required: true,
      target: "actionAddress",
    },
    { action: "URL", kind: "url", label: "URL", required: true, target: "actionAddress" },
  ] as const)(
    "$action needs a $kind field named $label",
    ({ action, kind, label, required, target }) => {
      const field = actionFieldFor(action);

      expect(field?.kind).toBe(kind);
      expect(field?.label).toBe(label);
      expect(field?.required).toBe(required);
      expect(field?.target).toBe(target);
    },
  );

  it.each([{ action: "POLL" }, { action: "SEND_TO_MESSENGER" }] as const)(
    "$action has no action-specific field",
    ({ action }) => {
      expect(actionFieldFor(action)).toBeNull();
    },
  );

  it("gives EMAIL_USER's back-up email field a fallback helper", () => {
    expect(actionFieldFor("EMAIL_USER")?.helper).toBe(
      "This email will be forwarded to only in case account user email cannot be found.",
    );
  });
});

describe("toggledInboundRule", () => {
  it.each([
    { enabled: true, expected: false, label: "an enabled rule is sent disabled" },
    { enabled: false, expected: true, label: "a disabled rule is sent enabled" },
  ] as const)("$label", ({ enabled, expected }) => {
    expect(toggledInboundRule({ ...DEFAULT_RULE, enabled })).toEqual({
      input: {
        action: "EMAIL_USER",
        actionAddress: null,
        backupEmail: null,
        enabled: expected,
        keyword: null,
        matchKind: "ANY",
        name: "Default rule",
        number: null,
      },
      ruleId: "rule-default",
    });
  });
});
