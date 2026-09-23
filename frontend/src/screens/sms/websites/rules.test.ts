import { describe, expect, it } from "vitest";

import { isValidDomain, normaliseDomain } from "./rules";

describe("normaliseDomain", () => {
  it.each([
    { input: "junaid.guru", label: "a bare domain is unchanged", output: "junaid.guru" },
    { input: "https://junaid.guru", label: "strips the https scheme", output: "junaid.guru" },
    { input: "http://junaid.guru", label: "strips the http scheme", output: "junaid.guru" },
    { input: "junaid.guru/about", label: "strips a path", output: "junaid.guru" },
    { input: "junaid.guru?ref=1", label: "strips a query string", output: "junaid.guru" },
    { input: "junaid.guru#section", label: "strips a fragment", output: "junaid.guru" },
    { input: "JUNAID.GURU", label: "lowercases the domain", output: "junaid.guru" },
    { input: "junaid.guru.", label: "strips a trailing dot", output: "junaid.guru" },
    {
      input: "www.junaid.guru",
      label: "keeps the www subdomain distinct from the bare domain",
      output: "www.junaid.guru",
    },
    { input: "  junaid.guru  ", label: "trims surrounding whitespace", output: "junaid.guru" },
  ] as const)("$label", ({ input, output }) => {
    expect(normaliseDomain(input)).toBe(output);
  });
});

describe("isValidDomain", () => {
  it.each([
    { domain: "junaid.guru", label: "a normal domain is valid", valid: true },
    { domain: "www.junaid.guru", label: "a subdomain is valid", valid: true },
    { domain: "", label: "an empty string is invalid", valid: false },
    { domain: "not a domain", label: "a string with spaces is invalid", valid: false },
    { domain: "localhost", label: "a hostname without a dot is invalid", valid: false },
    { domain: "-junaid.guru", label: "a leading hyphen is invalid", valid: false },
  ] as const)("$label", ({ domain, valid }) => {
    expect(isValidDomain(domain)).toBe(valid);
  });
});
