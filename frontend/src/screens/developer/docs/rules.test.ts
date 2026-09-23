import { describe, expect, it } from "vitest";

import { OPENAPI_FIXTURE } from "@/test/fixtures/developer";

import type { JsonSchema, OpenApiDocument } from "./rules";
import { describeType, fieldsOf, groupedOperations } from "./rules";

describe("describeType", () => {
  const schemas: Record<string, JsonSchema> = {
    Direction: { enum: ["IN", "OUT"], title: "Direction", type: "string" },
    V3List: { properties: {}, title: "V3List", type: "object" },
  };

  it.each([
    { expected: "string", label: "a plain type", schema: { type: "string" } },
    {
      expected: "V3List",
      label: "a $ref to an object schema",
      schema: { $ref: "#/components/schemas/V3List" },
    },
    {
      expected: '"IN" | "OUT"',
      label: "a $ref to an enum schema shows its values",
      schema: { $ref: "#/components/schemas/Direction" },
    },
    {
      expected: "array of V3List",
      label: "an array shows what it holds",
      schema: { items: { $ref: "#/components/schemas/V3List" }, type: "array" },
    },
    {
      expected: "string | null",
      label: "a nullable anyOf keeps the real type and appends null",
      schema: { anyOf: [{ type: "string" }, { type: "null" }] },
    },
    {
      expected: "object",
      label: "a free-form map",
      schema: { additionalProperties: { type: "string" }, type: "object" },
    },
  ] as const)("$label", ({ expected, schema }) => {
    expect(describeType(schema, schemas)).toBe(expected);
  });
});

describe("fieldsOf", () => {
  it("lists required and optional fields alphabetically with their types", () => {
    const schema: JsonSchema = {
      properties: {
        b: { type: "string" },
        a: { type: "integer" },
      },
      required: ["a"],
    };

    expect(fieldsOf(schema, {})).toEqual([
      { name: "a", required: true, type: "integer" },
      { name: "b", required: false, type: "string" },
    ]);
  });

  it("returns nothing for a schema with no properties", () => {
    expect(fieldsOf({}, {})).toEqual([]);
  });
});

describe("groupedOperations", () => {
  it("groups by the first path segment, labelled and sorted alphabetically", () => {
    const groups = groupedOperations(OPENAPI_FIXTURE);

    expect(groups.map((group) => group.label)).toEqual(["Account", "Lists"]);
  });

  it("resolves the response schema fields for a $ref'd object", () => {
    const [account] = groupedOperations(OPENAPI_FIXTURE);

    expect(account?.operations[0]?.responseFields).toEqual([
      { name: "balance", required: true, type: "string" },
      { name: "currency", required: true, type: "string" },
    ]);
  });

  it("notes an empty response schema instead of showing a blank table", () => {
    const lists = groupedOperations(OPENAPI_FIXTURE).find((group) => group.label === "Lists");

    expect(lists?.operations[0]?.responseFields).toEqual([]);
    expect(lists?.operations[0]?.responseNote).toBe("No fields to show.");
  });

  it("skips a document with no matching group", () => {
    const empty: OpenApiDocument = { paths: {} };

    expect(groupedOperations(empty)).toEqual([]);
  });
});
