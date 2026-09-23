const HTTP_METHODS = new Set(["delete", "get", "patch", "post", "put"]);
const NO_SCHEMA_FIELDS_MSG = "No fields to show.";
const NULL_TYPE = "null";
const REF_PREFIX = "#/components/schemas/";
const V3_PATH_PREFIX = "/api/v3/";

export interface JsonSchema {
  $ref?: string;
  additionalProperties?: JsonSchema | boolean;
  anyOf?: readonly JsonSchema[];
  enum?: readonly (number | string)[];
  items?: JsonSchema;
  properties?: Record<string, JsonSchema>;
  required?: readonly string[];
  title?: string;
  type?: string;
}

interface OpenApiOperation {
  requestBody?: { content: { "application/json": { schema: JsonSchema } } };
  responses: Record<string, { content?: { "application/json": { schema: JsonSchema } } }>;
  summary?: string;
}

export interface OpenApiDocument {
  components?: { schemas?: Record<string, JsonSchema> };
  paths: Record<string, Record<string, OpenApiOperation>>;
}

export interface SchemaField {
  name: string;
  required: boolean;
  type: string;
}

export interface RenderedOperation {
  method: string;
  path: string;
  requestFields: SchemaField[] | undefined;
  requestNote: string | undefined;
  responseFields: SchemaField[] | undefined;
  responseNote: string | undefined;
  summary: string | undefined;
}

interface OperationGroup {
  label: string;
  operations: readonly RenderedOperation[];
}

function refName(ref: string): string {
  return ref.startsWith(REF_PREFIX) ? ref.slice(REF_PREFIX.length) : ref;
}

function resolvedSchema(schema: JsonSchema, schemas: Record<string, JsonSchema>): JsonSchema {
  return schema.$ref === undefined ? schema : (schemas[refName(schema.$ref)] ?? schema);
}

function describeRef(ref: string, resolved: JsonSchema): string {
  return resolved.enum === undefined
    ? refName(ref)
    : resolved.enum.map((value) => JSON.stringify(value)).join(" | ");
}

function describeArrayItems(
  items: JsonSchema | undefined,
  schemas: Record<string, JsonSchema>,
): string {
  return items === undefined ? "unknown" : describeType(items, schemas);
}

export function describeType(schema: JsonSchema, schemas: Record<string, JsonSchema>): string {
  if (schema.$ref !== undefined) {
    return describeRef(schema.$ref, resolvedSchema(schema, schemas));
  }
  if (schema.anyOf !== undefined) {
    return describeAnyOf(schema.anyOf, schemas);
  }
  if (schema.type === "array") {
    return `array of ${describeArrayItems(schema.items, schemas)}`;
  }
  if (schema.type === "object" && schema.additionalProperties !== undefined) {
    return "object";
  }

  return schema.type ?? "unknown";
}

function describeAnyOf(
  branches: readonly JsonSchema[],
  schemas: Record<string, JsonSchema>,
): string {
  const named = branches.filter((branch) => branch.type !== NULL_TYPE);
  const nullable = named.length !== branches.length;
  const described = named.map((branch) => describeType(branch, schemas)).join(" | ");

  return nullable ? `${described} | null` : described;
}

export function fieldsOf(schema: JsonSchema, schemas: Record<string, JsonSchema>): SchemaField[] {
  const resolved = resolvedSchema(schema, schemas);
  if (resolved.properties === undefined) {
    return [];
  }
  const required = new Set(resolved.required ?? []);

  return Object.entries(resolved.properties)
    .map(([name, propSchema]) => ({
      name,
      required: required.has(name),
      type: describeType(propSchema, schemas),
    }))
    .sort((left, right) => left.name.localeCompare(right.name));
}

function refNamesIfAllRefs(branches: readonly JsonSchema[]): string[] | undefined {
  const names: string[] = [];
  for (const branch of branches) {
    if (branch.$ref === undefined) {
      return undefined;
    }
    names.push(refName(branch.$ref));
  }

  return names;
}

function noteFor(
  schema: JsonSchema | undefined,
  fields: SchemaField[] | undefined,
): string | undefined {
  if (schema === undefined || fields === undefined) {
    return undefined;
  }
  if (schema.anyOf !== undefined) {
    const names = refNamesIfAllRefs(schema.anyOf);
    if (names !== undefined) {
      return `One of: ${names.join(", ")}`;
    }
  }

  return fields.length === 0 ? NO_SCHEMA_FIELDS_MSG : undefined;
}

function twoXxSchema(responses: OpenApiOperation["responses"]): JsonSchema | undefined {
  for (const [code, response] of Object.entries(responses)) {
    if (code.startsWith("2")) {
      return response.content?.["application/json"].schema;
    }
  }

  return undefined;
}

function operationOf(
  method: string,
  path: string,
  operation: OpenApiOperation,
  schemas: Record<string, JsonSchema>,
): RenderedOperation {
  const bodySchema = operation.requestBody?.content["application/json"].schema;
  const responseSchema = twoXxSchema(operation.responses);
  const requestFields = bodySchema === undefined ? undefined : fieldsOf(bodySchema, schemas);
  const responseFields =
    responseSchema === undefined ? undefined : fieldsOf(responseSchema, schemas);

  return {
    method: method.toUpperCase(),
    path,
    requestFields,
    requestNote: noteFor(bodySchema, requestFields),
    responseFields,
    responseNote: noteFor(responseSchema, responseFields),
    summary: operation.summary,
  };
}

function groupLabelOf(path: string): string {
  const withoutPrefix = path.startsWith(V3_PATH_PREFIX) ? path.slice(V3_PATH_PREFIX.length) : path;
  const segment = withoutPrefix.split("/")[0] ?? withoutPrefix;

  return segment
    .split("-")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

function sortKey(operation: RenderedOperation): string {
  return `${operation.path} ${operation.method}`;
}

export function groupedOperations(document: OpenApiDocument): OperationGroup[] {
  const schemas = document.components?.schemas ?? {};
  const groups = new Map<string, RenderedOperation[]>();

  for (const [path, methods] of Object.entries(document.paths)) {
    for (const [method, operation] of Object.entries(methods)) {
      if (!HTTP_METHODS.has(method)) {
        continue;
      }
      const label = groupLabelOf(path);
      const existing = groups.get(label) ?? [];
      existing.push(operationOf(method, path, operation, schemas));
      groups.set(label, existing);
    }
  }

  return [...groups.entries()]
    .map(([label, operations]) => ({
      label,
      operations: operations.sort((left, right) => sortKey(left).localeCompare(sortKey(right))),
    }))
    .sort((left, right) => left.label.localeCompare(right.label));
}
