export interface RuleEdit<Request> {
  input: Request;
  ruleId: string;
}

export function ruleUpdateOf<Request>(edit: RuleEdit<Request>) {
  return { body: edit.input, params: { path: { ruleId: edit.ruleId } } };
}
