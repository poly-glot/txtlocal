import { describe, expect, it } from "vitest";

import type { Recipient } from "../rules";
import { MAX_RECIPIENTS, TOO_MANY_RECIPIENTS_MSG, addRecipient } from "./rules";

describe("addRecipient", () => {
  const chipsOf = (count: number): Recipient[] =>
    Array.from({ length: count }, (_, index) => ({
      kind: "NUMBER",
      label: String(index),
      value: String(index),
    }));

  it("accepts the thousandth recipient", () => {
    const added = addRecipient(chipsOf(MAX_RECIPIENTS - 1), {
      kind: "NUMBER",
      label: "+447400123105",
      value: "+447400123105",
    });

    expect(added).toEqual({
      data: [
        ...chipsOf(MAX_RECIPIENTS - 1),
        { kind: "NUMBER", label: "+447400123105", value: "+447400123105" },
      ],
      status: "OK",
    });
  });

  it("refuses the thousand-and-first recipient", () => {
    const added = addRecipient(chipsOf(MAX_RECIPIENTS), {
      kind: "NUMBER",
      label: "+447400123105",
      value: "+447400123105",
    });

    expect(added).toEqual({
      message: "Send to at most 1,000 recipients at a time",
      status: "ERROR",
    });
    expect(TOO_MANY_RECIPIENTS_MSG).toBe("Send to at most 1,000 recipients at a time");
  });

  it("keeps one chip per number", () => {
    const chip: Recipient = { kind: "NUMBER", label: "07411972333", value: "07411972333" };

    expect(addRecipient([chip], chip)).toEqual({ data: [chip], status: "OK" });
  });
});
