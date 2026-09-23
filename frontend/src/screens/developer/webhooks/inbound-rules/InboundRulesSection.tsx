import { useApiQuery } from "@/api/queries";
import { StatusPanel } from "@/components/StatusPanel/StatusPanel";

import { InboundRulesPanel } from "./InboundRulesPanel";

const HEADING = "Inbound Rules";

export function InboundRulesSection() {
  const rules = useApiQuery("get", "/api/app/rules/inbound");

  if (rules.data === undefined) {
    return <StatusPanel title={HEADING} />;
  }
  if (rules.data.status === "ERROR") {
    return <StatusPanel error={rules.data.message} title={HEADING} />;
  }

  return <InboundRulesPanel rules={rules.data.data} title={HEADING} />;
}
